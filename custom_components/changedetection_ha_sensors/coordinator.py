"""Coordinator: legge i watch e, solo per quelli cambiati, l'ultima rilevazione e il prezzo precedente."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ChangedetectionClient, ChangedetectionError, InvalidAuth
from .const import (
    CONF_EXCLUDED,
    CONF_HISTORY_DEPTH,
    CONF_SCAN_INTERVAL,
    DOMAIN,
    EVENT_CHANGE,
    LOGGER,
    MAX_PARALLEL,
    SNAPSHOT_MAX_CHARS,
    int_option,
)
from .parse import clean_text, extract_price, extract_stock, trend


@dataclass
class Watch:
    """Stato di un watch, come lo vedono entita' e card."""

    uuid: str
    title: str
    url: str
    last_changed: datetime | None = None
    last_checked: datetime | None = None
    paused: bool = False
    error: str | None = None
    viewed: bool = True
    tags: list[str] = field(default_factory=list)
    text: str = ""
    price: float | None = None
    old_price: float | None = None
    in_stock: bool | None = None

    @property
    def trend(self) -> str | None:
        return trend(self.price, self.old_price)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["trend"] = self.trend
        for key in ("last_changed", "last_checked"):
            data[key] = data[key].isoformat() if data[key] else None
        return data


def _ts(value: Any) -> datetime | None:
    try:
        value = int(value or 0)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(value, UTC) if value > 0 else None


type ChangedetectionConfigEntry = ConfigEntry[ChangedetectionCoordinator]


class ChangedetectionCoordinator(DataUpdateCoordinator[dict[str, Watch]]):
    config_entry: ChangedetectionConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ChangedetectionConfigEntry, client: ChangedetectionClient) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=int_option(entry.options, CONF_SCAN_INTERVAL)),
        )
        self.client = client
        # uuid -> last_changed gia' elaborato: si rilegge lo storico solo quando cambia
        self._seen: dict[str, datetime | None] = {}
        self._first = True

    @property
    def excluded(self) -> set[str]:
        return set(self.config_entry.options.get(CONF_EXCLUDED, []))

    async def _async_update_data(self) -> dict[str, Watch]:
        try:
            raw = await self.client.async_get_watches()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed("Chiave API non valida") from err
        except ChangedetectionError as err:
            raise UpdateFailed(f"Errore di comunicazione con changedetection.io: {err}") from err

        previous = self.data or {}
        result: dict[str, Watch] = {}
        to_refresh: list[Watch] = []
        for uuid, info in raw.items():
            if uuid in self.excluded or not isinstance(info, dict):
                continue
            watch = Watch(
                uuid=uuid,
                title=info.get("title") or info.get("page_title") or info.get("url") or uuid,
                url=info.get("link") or info.get("url") or "",
                last_changed=_ts(info.get("last_changed")),
                last_checked=_ts(info.get("last_checked")),
                paused=bool(info.get("paused")),
                error=info.get("last_error") or None,
                viewed=bool(info.get("viewed", True)),
                tags=list(info.get("tags") or []),
            )
            old = previous.get(uuid)
            if old is not None:
                # Valori gia' letti: restano anche se la nuova lettura delle rilevazioni fallisce
                watch.text, watch.price, watch.old_price, watch.in_stock = (
                    old.text,
                    old.price,
                    old.old_price,
                    old.in_stock,
                )
            if old is None or self._seen.get(uuid) != watch.last_changed:
                to_refresh.append(watch)
            result[uuid] = watch

        semaphore = asyncio.Semaphore(MAX_PARALLEL)

        async def refresh(watch: Watch) -> None:
            async with semaphore:
                try:
                    await self._async_read_snapshots(watch)
                except ChangedetectionError as err:
                    LOGGER.warning("Rilevazioni di '%s' non lette: %s", watch.title, err)
                    return
            changed = (not self._first) and watch.uuid in self._seen and self._seen[watch.uuid] != watch.last_changed
            self._seen[watch.uuid] = watch.last_changed
            if changed:
                self.hass.bus.async_fire(EVENT_CHANGE, watch.as_dict())

        await asyncio.gather(*(refresh(w) for w in to_refresh))
        self._first = False
        return result

    async def _async_read_snapshots(self, watch: Watch) -> None:
        """Ultima rilevazione e, risalendo lo storico, il primo prezzo diverso da quello attuale."""
        if watch.last_changed is None:
            return
        history = await self.client.async_get_history(watch.uuid)
        if not history:
            return
        latest = await self.client.async_get_snapshot(watch.uuid, history[0])
        watch.text = clean_text(latest, SNAPSHOT_MAX_CHARS)
        watch.price = extract_price(latest)
        watch.in_stock = extract_stock(latest)
        watch.old_price = None
        if watch.price is None:
            return
        depth = int_option(self.config_entry.options, CONF_HISTORY_DEPTH)
        for timestamp in history[1 : depth + 1]:
            price = extract_price(await self.client.async_get_snapshot(watch.uuid, timestamp))
            if price is not None and price != watch.price:
                watch.old_price = price
                break

    def recent(self, limit: int) -> list[Watch]:
        """Watch ordinati dall'ultima modifica, i primi `limit`."""
        watches = [w for w in (self.data or {}).values() if w.last_changed]
        watches.sort(key=lambda w: w.last_changed, reverse=True)
        return watches[:limit]
