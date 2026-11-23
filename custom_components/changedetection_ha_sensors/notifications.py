"""Notifiche: regole (tipo di modifica, soglie, prezzo obiettivo, attesa, ore di silenzio) e invio ai servizi notify."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_COOLDOWN_HOURS,
    CONF_CURRENCY,
    CONF_MIN_DROP_AMOUNT,
    CONF_MIN_DROP_PERCENT,
    CONF_NOTIFY_ON,
    CONF_NOTIFY_TARGETS,
    CONF_QUIET_END,
    CONF_QUIET_START,
    DEFAULT_COOLDOWN_HOURS,
    DEFAULT_CURRENCY,
    DEFAULT_NOTIFY_ON,
    DOMAIN,
    LOGGER,
    NOTIFY_BACK_IN_STOCK,
    NOTIFY_CHANGE,
    NOTIFY_DOWN,
    NOTIFY_UP,
)
from .coordinator import Watch

STORE_VERSION = 1
SAVE_DELAY = 5

TEXTS = {
    "it": {
        NOTIFY_DOWN: "📉 {title}",
        NOTIFY_UP: "📈 {title}",
        NOTIFY_BACK_IN_STOCK: "✅ {title}",
        NOTIFY_CHANGE: "🔔 {title}",
        "back_msg": "Di nuovo disponibile",
        "change_msg": "La pagina è cambiata",
        "test_title": "Changedetection HA sensors",
        "test_msg": "Notifica di prova: i destinatari sono configurati correttamente.",
    },
    "en": {
        NOTIFY_DOWN: "📉 {title}",
        NOTIFY_UP: "📈 {title}",
        NOTIFY_BACK_IN_STOCK: "✅ {title}",
        NOTIFY_CHANGE: "🔔 {title}",
        "back_msg": "Back in stock",
        "change_msg": "The page has changed",
        "test_title": "Changedetection HA sensors",
        "test_msg": "Test notification: the recipients are set up correctly.",
    },
}


@dataclass
class Notification:
    uuid: str
    title: str
    message: str
    url: str
    price: float | None

    def as_dict(self) -> dict[str, Any]:
        return {"uuid": self.uuid, "title": self.title, "message": self.message, "url": self.url, "price": self.price}


def _parse_time(value: Any) -> time | None:
    if not value:
        return None
    try:
        return time.fromisoformat(str(value))
    except ValueError:
        return None


def in_quiet_hours(now: time, start: time | None, end: time | None) -> bool:
    """Fascia [start, end), anche a cavallo della mezzanotte (23:00-08:00)."""
    if start is None or end is None or start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def classify(old: Watch | None, new: Watch) -> tuple[str, float | None]:
    """(tipo di modifica, prezzo di confronto)."""
    if old is not None and old.in_stock is False and new.in_stock is True:
        reference = old.price
        return NOTIFY_BACK_IN_STOCK, reference
    reference = old.price if old is not None and old.price is not None else new.old_price
    if new.price is not None and reference is not None and new.price != reference:
        return (NOTIFY_DOWN if new.price < reference else NOTIFY_UP), reference
    return NOTIFY_CHANGE, reference


class NotificationManager:
    """Decide se avvisare e invia.

    Stato persistente: preferenze per watch, ultimo avviso, coda delle ore di silenzio.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str, options: dict[str, Any]) -> None:
        self.hass = hass
        self.options = options
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry_id}.notifications")
        self._watches: dict[str, dict[str, Any]] = {}  # uuid -> {enabled, target, last_sent, last_price}
        self._queue: dict[str, dict[str, Any]] = {}  # uuid -> Notification.as_dict() rimandata
        self._unsub: CALLBACK_TYPE | None = None
        self.now: Callable[[], datetime] = dt_util.now

    # ---- stato

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self._watches = data.get("watches", {})
        self._queue = data.get("queue", {})
        end = _parse_time(self.options.get(CONF_QUIET_END))
        if end is not None:
            self._unsub = async_track_time_change(
                self.hass, self._async_flush_at, hour=end.hour, minute=end.minute, second=0
            )
        if self._queue and not self._quiet():
            self.hass.async_create_task(self.async_flush())

    async def async_unload(self) -> None:
        """Allo scaricamento (ricarica, opzioni) si salva subito: il salvataggio ritardato andrebbe perso."""
        if self._unsub:
            self._unsub()
            self._unsub = None
        await self._store.async_save(self._data())

    def _data(self) -> dict[str, Any]:
        return {"watches": self._watches, "queue": self._queue}

    def _save(self) -> None:
        self._store.async_delay_save(self._data, SAVE_DELAY)

    def _prefs(self, uuid: str) -> dict[str, Any]:
        return self._watches.setdefault(uuid, {"enabled": True, "target": None})

    def enabled(self, uuid: str) -> bool:
        return self._watches.get(uuid, {}).get("enabled", True)

    def target(self, uuid: str) -> float | None:
        return self._watches.get(uuid, {}).get("target")

    @callback
    def set_enabled(self, uuid: str, enabled: bool) -> None:
        self._prefs(uuid)["enabled"] = enabled
        self._save()

    @callback
    def set_target(self, uuid: str, target: float | None) -> None:
        self._prefs(uuid)["target"] = target if target else None
        self._save()

    # ---- regole

    def _quiet(self) -> bool:
        return in_quiet_hours(
            self.now().time(),
            _parse_time(self.options.get(CONF_QUIET_START)),
            _parse_time(self.options.get(CONF_QUIET_END)),
        )

    def _lang(self) -> dict[str, str]:
        return TEXTS.get((self.hass.config.language or "en").split("-")[0], TEXTS["en"])

    def _money(self, value: float) -> str:
        currency = self.options.get(CONF_CURRENCY, DEFAULT_CURRENCY)
        symbol = {"EUR": "€", "USD": "$", "GBP": "£", "CHF": "CHF"}.get(currency.upper(), currency)
        if (self.hass.config.language or "en").startswith("it"):
            number = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"{number} {symbol}"
        return f"{symbol}{value:,.2f}"

    def evaluate(self, old: Watch | None, new: Watch) -> Notification | None:
        """La notifica da inviare per questa modifica, o None (con il motivo nel log di debug)."""
        if not self.options.get(CONF_NOTIFY_TARGETS):
            return None
        if not self.enabled(new.uuid):
            LOGGER.debug("%s: notifiche spente per questo watch", new.title)
            return None
        kind, reference = classify(old, new)
        if kind not in self.options.get(CONF_NOTIFY_ON, DEFAULT_NOTIFY_ON):
            LOGGER.debug("%s: modifica '%s' non scelta tra quelle da notificare", new.title, kind)
            return None

        if kind == NOTIFY_DOWN and reference:
            drop = reference - new.price
            if drop < float(self.options.get(CONF_MIN_DROP_AMOUNT, 0) or 0):
                LOGGER.debug("%s: ribasso di %.2f sotto la soglia", new.title, drop)
                return None
            if drop / reference * 100 < float(self.options.get(CONF_MIN_DROP_PERCENT, 0) or 0):
                LOGGER.debug("%s: ribasso del %.1f%% sotto la soglia", new.title, drop / reference * 100)
                return None

        target = self.target(new.uuid)
        if target is not None and (new.price is None or new.price > target):
            LOGGER.debug("%s: prezzo %s sopra l'obiettivo %s", new.title, new.price, target)
            return None

        prefs = self._watches.get(new.uuid, {})
        cooldown = float(self.options.get(CONF_COOLDOWN_HOURS, DEFAULT_COOLDOWN_HOURS) or 0)
        if cooldown and prefs.get("last_sent"):
            last = dt_util.parse_datetime(prefs["last_sent"])
            lower = new.price is not None and prefs.get("last_price") is not None and new.price < prefs["last_price"]
            if last and self.now() - last < timedelta(hours=cooldown) and not lower:
                LOGGER.debug("%s: gia' avvisato da meno di %s ore", new.title, cooldown)
                return None

        texts = self._lang()
        if kind in (NOTIFY_DOWN, NOTIFY_UP) and reference:
            percent = (new.price - reference) / reference * 100
            message = f"{self._money(reference)} → {self._money(new.price)} ({percent:+.0f}%)"
        elif kind == NOTIFY_BACK_IN_STOCK:
            message = texts["back_msg"] + (f" · {self._money(new.price)}" if new.price is not None else "")
        elif new.price is not None:
            message = self._money(new.price)
        else:
            message = new.text[:200] or texts["change_msg"]
        return Notification(new.uuid, texts[kind].format(title=new.title), message, new.url, new.price)

    # ---- invio

    async def async_handle_change(self, old: Watch | None, new: Watch) -> None:
        notification = self.evaluate(old, new)
        if notification is None:
            return
        prefs = self._prefs(new.uuid)
        prefs["last_sent"] = self.now().isoformat()
        prefs["last_price"] = new.price
        if self._quiet():
            LOGGER.debug("%s: ore di silenzio, notifica rimandata", new.title)
            self._queue[new.uuid] = notification.as_dict()  # per watch vale l'ultima
            self._save()
            return
        self._save()
        await self._async_send(notification.title, notification.message, notification.url)

    @callback
    def _async_flush_at(self, _now: datetime) -> None:
        self.hass.async_create_task(self.async_flush())

    async def async_flush(self) -> None:
        """Invia gli avvisi rimandati durante le ore di silenzio."""
        queue, self._queue = self._queue, {}
        self._save()
        for item in queue.values():
            await self._async_send(item["title"], item["message"], item["url"])

    async def async_send_test(self) -> None:
        texts = self._lang()
        await self._async_send(texts["test_title"], texts["test_msg"], "")

    async def _async_send(self, title: str, message: str, url: str) -> None:
        data: dict[str, Any] = {"title": title, "message": message}
        if url:
            # url: app Companion iOS; clickAction: app Companion Android
            data["data"] = {"url": url, "clickAction": url}
        for target in self.options.get(CONF_NOTIFY_TARGETS, []):
            domain, _, service = target.partition(".")
            if domain != "notify" or not self.hass.services.has_service("notify", service):
                LOGGER.warning("Servizio di notifica %s non trovato", target)
                continue
            try:
                await self.hass.services.async_call("notify", service, data, blocking=True)
            except Exception:  # noqa: BLE001 - un destinatario rotto non blocca gli altri
                LOGGER.exception("Invio della notifica a %s non riuscito", target)
