"""Setup, entita', prezzo precedente, evento di modifica, pulsanti."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_capture_events, async_fire_time_changed

from custom_components.changedetection_ha_sensors.const import CONF_EXCLUDED, DOMAIN, EVENT_CHANGE

from .conftest import HELMET, NOW, PAGE, PLUG


def _entity(hass: HomeAssistant, uuid: str, key: str) -> str:
    return er.async_get(hass).async_get_entity_id("sensor" if key != "recheck" else "button", DOMAIN, f"{uuid}_{key}")


async def _setup(hass, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_prices(hass: HomeAssistant, server, entry) -> None:
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    helmet = hass.states.get(_entity(hass, HELMET, "price"))
    assert float(helmet.state) == 319.95
    assert helmet.attributes["unit_of_measurement"] == "EUR"
    # risale oltre la rilevazione con lo stesso prezzo (cambiata solo la disponibilita')
    assert helmet.attributes["previous_price"] == 229.95
    assert helmet.attributes["trend"] == "up"
    assert helmet.attributes["in_stock"] is True

    plug = hass.states.get(_entity(hass, PLUG, "price"))
    assert float(plug.state) == 22.79
    assert plug.attributes["previous_price"] == 23.99
    assert plug.attributes["trend"] == "down"

    page = hass.states.get(_entity(hass, PAGE, "price"))
    assert page.state == "unknown"
    changed = hass.states.get(_entity(hass, PAGE, "last_changed"))
    assert changed.attributes["text"] == "Nuovo articolo pubblicato"
    assert changed.attributes["error"] == "Timeout"


async def test_recent_changes(hass: HomeAssistant, server, entry) -> None:
    await _setup(hass, entry)
    recent = hass.states.get("sensor.changedetection_io_recent_changes")
    assert recent is not None
    assert dt_util.parse_datetime(recent.state).timestamp() == NOW - 60
    watches = recent.attributes["watches"]
    assert [w["uuid"] for w in watches] == [PAGE, HELMET, PLUG]
    assert watches[0]["title"] == "https://news.example/"  # senza titolo: l'URL
    assert recent.attributes["changedetection_card"] is True
    count = hass.states.get("sensor.changedetection_io_watches")
    assert count.state == "3"
    assert count.attributes["with_errors"] == 1
    assert count.attributes["unviewed"] == 1


async def test_change_event_and_cache(hass: HomeAssistant, server, entry) -> None:
    await _setup(hass, entry)
    events = async_capture_events(hass, EVENT_CHANGE)
    calls = server.snapshot_calls

    # nessun cambio: lo storico non viene riletto e nessun evento
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert server.snapshot_calls == calls
    assert events == []

    # il prezzo della presa scende
    server.history[PLUG][str(NOW + 100)] = "€19.99 €10.00"
    server.watches[PLUG]["last_changed"] = NOW + 100
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=12))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(events) == 1
    assert events[0].data["uuid"] == PLUG
    assert events[0].data["price"] == 19.99
    assert events[0].data["old_price"] == 22.79
    assert events[0].data["trend"] == "down"
    assert float(hass.states.get(_entity(hass, PLUG, "price")).state) == 19.99


async def test_new_watch_added(hass: HomeAssistant, server, entry) -> None:
    await _setup(hass, entry)
    uuid = "44444444-4444-4444-4444-444444444444"
    server.watches[uuid] = {"title": "Nuovo", "url": "https://x.example", "last_changed": NOW + 5}
    server.history[uuid] = {str(NOW + 5): "€5.00"}
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert float(hass.states.get(_entity(hass, uuid, "price")).state) == 5.0


async def test_excluded(hass: HomeAssistant, server, entry) -> None:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_EXCLUDED: [PAGE]})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _entity(hass, PAGE, "price") is None
    assert _entity(hass, HELMET, "price") is not None


async def test_buttons(hass: HomeAssistant, server, entry) -> None:
    await _setup(hass, entry)
    await hass.services.async_call("button", "press", {"entity_id": _entity(hass, HELMET, "recheck")}, blocking=True)
    server.client.async_recheck.assert_awaited_once_with(HELMET)
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.changedetection_io_recheck_all"}, blocking=True
    )
    server.client.async_recheck_all.assert_awaited_once()


async def test_auth_failure_starts_reauth(hass: HomeAssistant, server, entry) -> None:
    from custom_components.changedetection_ha_sensors.api import InvalidAuth

    server.client.async_get_watches.side_effect = InvalidAuth
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(flow["context"]["source"] == "reauth" for flow in hass.config_entries.flow.async_progress())


async def test_unload(hass: HomeAssistant, server, entry) -> None:
    await _setup(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
