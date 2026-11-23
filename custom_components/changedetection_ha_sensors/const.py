"""Costanti di Changedetection HA sensors."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "changedetection_ha_sensors"
NAME: Final = "Changedetection HA sensors"
VERSION: Final = "0.1.1"
LOGGER = logging.getLogger(__package__)

# Configurazione (data)
CONF_URL: Final = "url"
CONF_API_KEY: Final = "api_key"
CONF_VERIFY_SSL: Final = "verify_ssl"

# Opzioni
CONF_SCAN_INTERVAL: Final = "scan_interval"  # minuti
CONF_LIMIT: Final = "limit"  # voci nel sensore "Ultime modifiche"
CONF_EXCLUDED: Final = "excluded_watches"  # uuid esclusi
CONF_CURRENCY: Final = "currency"
CONF_HISTORY_DEPTH: Final = "history_depth"  # rilevazioni lette all'indietro per il prezzo precedente

DEFAULT_SCAN_INTERVAL: Final = 5
DEFAULT_LIMIT: Final = 10
DEFAULT_CURRENCY: Final = "EUR"
DEFAULT_HISTORY_DEPTH: Final = 10

# Evento lanciato quando una pagina cambia (non al primo caricamento)
EVENT_CHANGE: Final = f"{DOMAIN}_change"

# Card servita dall'integrazione
URL_BASE: Final = f"/{DOMAIN}"
CARD_FILE: Final = "changedetection-card.js"

# Richieste parallele al server durante l'aggiornamento
MAX_PARALLEL: Final = 4
SNAPSHOT_MAX_CHARS: Final = 1000
