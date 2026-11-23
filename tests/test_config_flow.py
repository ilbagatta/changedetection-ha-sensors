"""Configurazione, riautenticazione, riconfigurazione e opzioni."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.changedetection_ha_sensors.api import CannotConnect, InvalidAuth
from custom_components.changedetection_ha_sensors.const import (
    CONF_API_KEY,
    CONF_EXCLUDED,
    CONF_URL,
    CONF_VERIFY_SSL,
    DOMAIN,
)

from .conftest import HELMET

INPUT = {CONF_URL: "http://cd.local:5000/api/v1/", CONF_API_KEY: "abc", CONF_VERIFY_SSL: True}


async def test_user_flow(hass: HomeAssistant, server) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_URL] == "http://cd.local:5000"
    assert result["result"].unique_id == "http://cd.local:5000"


async def test_user_flow_errors(hass: HomeAssistant, server) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    server.client.async_system_info.side_effect = InvalidAuth
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["errors"] == {"base": "invalid_auth"}
    server.client.async_system_info.side_effect = CannotConnect
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["errors"] == {"base": "cannot_connect"}
    server.client.async_system_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(hass: HomeAssistant, server, entry) -> None:
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, server, entry) -> None:
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "nuova"})
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "nuova"


async def test_reconfigure(hass: HomeAssistant, server, entry) -> None:
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "http://cd.local:5000/", CONF_API_KEY: "k2", CONF_VERIFY_SSL: False}
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_API_KEY] == "k2"
    assert entry.data[CONF_VERIFY_SSL] is False


async def test_options(hass: HomeAssistant, server, entry) -> None:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={"limit": 10.0, "notify_targets": ["notify.phone"]})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "general"})
    assert result["step_id"] == "general"
    options = result["data_schema"].schema
    excluded = next(k for k in options if k == CONF_EXCLUDED)
    labels = {o["value"]: o["label"] for o in options[excluded].config["options"]}
    assert labels[HELMET] == "Casco"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        # come il frontend: il NumberSelector manda float
        {"scan_interval": 10.0, "history_depth": 10.0, "currency": "EUR", CONF_EXCLUDED: [HELMET]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_EXCLUDED] == [HELMET]
    assert entry.options["history_depth"] == 10
    assert isinstance(entry.options["history_depth"], int)
    assert "limit" not in entry.options  # opzione vecchia tolta
    assert entry.options["notify_targets"] == ["notify.phone"]  # l'altra pagina resta com'era
    assert entry.state is ConfigEntryState.LOADED


async def test_options_notifications(hass: HomeAssistant, server, entry) -> None:
    hass.services.async_register("notify", "phone", lambda call: None)
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={"quiet_start": "23:00:00", "quiet_end": "08:00:00"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "notifications"})
    assert result["step_id"] == "notifications"
    targets = next(k for k in result["data_schema"].schema if k == "notify_targets")
    assert "notify.phone" in result["data_schema"].schema[targets].config["options"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "notify_targets": ["notify.phone"],
            "notify_on": ["price_down"],
            "min_drop_percent": 5.0,
            "min_drop_amount": 0.0,
            "cooldown_hours": 6.0,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["notify_targets"] == ["notify.phone"]
    assert "quiet_start" not in entry.options  # lasciate vuote: tolte
    assert entry.state is ConfigEntryState.LOADED
