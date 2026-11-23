"""Costanti di Changedetection HA sensors."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Final

DOMAIN: Final = "changedetection_ha_sensors"
NAME: Final = "Changedetection HA sensors"
VERSION: Final = "0.2.0"
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
