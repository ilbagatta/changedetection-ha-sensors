"""Changedetection HA sensors: i watch di changedetection.io come sensori di Home Assistant, con card."""

from __future__ import annotations

import contextlib
from pathlib import Path

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import ChangedetectionClient
from .const import CARD_FILE, CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, DOMAIN, URL_BASE, VERSION
from .coordinator import ChangedetectionConfigEntry, ChangedetectionCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.BUTTON, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    await _async_register_card(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """La card e' servita dall'integrazione stessa: niente installazione separata."""
    if hass.http is None or "frontend" not in hass.config.components:
        return
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    path = Path(__file__).parent / "frontend"
    with contextlib.suppress(RuntimeError):  # gia' registrato
        await hass.http.async_register_static_paths([StaticPathConfig(URL_BASE, str(path), False)])
    add_extra_js_url(hass, f"{URL_BASE}/{CARD_FILE}?v={VERSION}")


async def async_setup_entry(hass: HomeAssistant, entry: ChangedetectionConfigEntry) -> bool:
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    client = ChangedetectionClient(session, entry.data[CONF_URL], entry.data[CONF_API_KEY])
    coordinator = ChangedetectionCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ChangedetectionConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ChangedetectionConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ChangedetectionConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Si puo' rimuovere a mano il dispositivo di un watch che non esiste piu' (o escluso)."""
    data = entry.runtime_data.data or {}
    return not any(ident[0] == DOMAIN and ident[1] in data for ident in device.identifiers)
