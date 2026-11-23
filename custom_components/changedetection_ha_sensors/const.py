"""Costanti di Changedetection HA sensors."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Final

DOMAIN: Final = "changedetection_ha_sensors"
NAME: Final = "Changedetection HA sensors"
VERSION: Final = "0.3.0"
LOGGER = logging.getLogger(__package__)

# Configurazione (data)
CONF_URL: Final = "url"
CONF_API_KEY: Final = "api_key"
CONF_VERIFY_SSL: Final = "verify_ssl"

# Opzioni
CONF_SCAN_INTERVAL: Final = "scan_interval"  # minuti
CONF_EXCLUDED: Final = "excluded_watches"  # uuid esclusi
CONF_CURRENCY: Final = "currency"
CONF_HISTORY_DEPTH: Final = "history_depth"  # rilevazioni lette all'indietro per il prezzo precedente

# Notifiche (opzioni)
CONF_NOTIFY_TARGETS: Final = "notify_targets"  # ["notify.mobile_app_x", ...]
CONF_NOTIFY_ON: Final = "notify_on"  # tipi di modifica da notificare
CONF_MIN_DROP_PERCENT: Final = "min_drop_percent"
CONF_MIN_DROP_AMOUNT: Final = "min_drop_amount"
CONF_COOLDOWN_HOURS: Final = "cooldown_hours"
CONF_QUIET_START: Final = "quiet_start"
CONF_QUIET_END: Final = "quiet_end"

NOTIFY_DOWN: Final = "price_down"
NOTIFY_UP: Final = "price_up"
NOTIFY_BACK_IN_STOCK: Final = "back_in_stock"
NOTIFY_CHANGE: Final = "any_change"
NOTIFY_KINDS: Final = [NOTIFY_DOWN, NOTIFY_UP, NOTIFY_BACK_IN_STOCK, NOTIFY_CHANGE]
DEFAULT_NOTIFY_ON: Final = [NOTIFY_DOWN, NOTIFY_BACK_IN_STOCK]
DEFAULT_COOLDOWN_HOURS: Final = 6

SERVICE_TEST_NOTIFICATION: Final = "test_notification"

DEFAULT_SCAN_INTERVAL: Final = 5
DEFAULT_CURRENCY: Final = "EUR"
DEFAULT_HISTORY_DEPTH: Final = 10

# Evento lanciato quando una pagina cambia (non al primo caricamento)
EVENT_CHANGE: Final = f"{DOMAIN}_change"

# Card servita dall'integrazione
URL_BASE: Final = f"/{DOMAIN}"
CARD_FILE: Final = "changedetection-card.js"

INT_OPTIONS: Final = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_HISTORY_DEPTH: DEFAULT_HISTORY_DEPTH,
}


def int_option(options: Mapping[str, Any], key: str) -> int:
    """Opzione numerica come intero: il NumberSelector salva float (10.0), le slice vogliono int."""
    try:
        return max(1, int(options.get(key, INT_OPTIONS[key])))
    except (TypeError, ValueError):
        return INT_OPTIONS[key]


# Voci al massimo nell'attributo `watches` di "Recent changes" (la card sceglie quante mostrarne)
MAX_LIST_ITEMS: Final = 100

# Richieste parallele al server durante l'aggiornamento
MAX_PARALLEL: Final = 4
SNAPSHOT_MAX_CHARS: Final = 1000
