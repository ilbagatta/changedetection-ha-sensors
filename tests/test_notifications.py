"""Notifiche: regole, prezzo obiettivo, interruttore, attesa, ore di silenzio, servizio di prova."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from custom_components.changedetection_ha_sensors.const import DOMAIN
from custom_components.changedetection_ha_sensors.coordinator import Watch
from custom_components.changedetection_ha_sensors.notifications import classify, in_quiet_hours

from .conftest import HELMET, NOW, PAGE, PLUG

BASE = {"notify_targets": ["notify.phone"], "notify_on": ["price_down", "back_in_stock"], "cooldown_hours": 0}


def _id(hass: HomeAssistant, platform: str, uuid: str, key: str) -> str:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{uuid}_{key}")


async def _setup(hass, entry, **options):
    calls = async_mock_service(hass, "notify", "phone")
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={**BASE, **options})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return calls


async def _change(hass, server, uuid: str, text: str, minutes: int = 6, offset: int = 100) -> None:
    server.history[uuid][str(NOW + offset)] = text
    server.watches[uuid]["last_changed"] = NOW + offset
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=minutes))
    await hass.async_block_till_done(wait_background_tasks=True)


def test_quiet_hours():
    t = datetime.strptime
    start, end = t("23:00", "%H:%M").time(), t("08:00", "%H:%M").time()
    assert in_quiet_hours(t("23:30", "%H:%M").time(), start, end)
    assert in_quiet_hours(t("07:59", "%H:%M").time(), start, end)
    assert not in_quiet_hours(t("08:00", "%H:%M").time(), start, end)
    assert not in_quiet_hours(t("12:00", "%H:%M").time(), start, end)
    assert in_quiet_hours(t("13:00", "%H:%M").time(), t("12:00", "%H:%M").time(), t("14:00", "%H:%M").time())
    assert not in_quiet_hours(t("13:00", "%H:%M").time(), None, end)


def test_classify():
    old = Watch("u", "t", "", price=10.0, in_stock=False)
    assert classify(old, Watch("u", "t", "", price=8.0, in_stock=True))[0] == "back_in_stock"
    old.in_stock = True
    assert classify(old, Watch("u", "t", "", price=8.0, in_stock=True)) == ("price_down", 10.0)
    assert classify(old, Watch("u", "t", "", price=12.0))[0] == "price_up"
    assert classify(old, Watch("u", "t", "", price=10.0))[0] == "any_change"
    assert classify(None, Watch("u", "t", "", price=9.0, old_price=10.0))[0] == "price_down"


async def test_price_drop_notifies(hass: HomeAssistant, server, entry) -> None:
    hass.config.language = "it"
    calls = await _setup(hass, entry)
    await _change(hass, server, PLUG, "€19.99")
    assert len(calls) == 1
    assert calls[0].data["title"] == "📉 Presa | smart"
    assert calls[0].data["message"] == "22,79 € → 19,99 € (-12%)"
    assert calls[0].data["data"] == {"url": "https://shop.example/presa", "clickAction": "https://shop.example/presa"}


async def test_price_up_not_notified_by_default(hass: HomeAssistant, server, entry) -> None:
    calls = await _setup(hass, entry)
    await _change(hass, server, PLUG, "€29.99")
    assert calls == []


async def test_no_targets_no_notifications(hass: HomeAssistant, server, entry) -> None:
    calls = await _setup(hass, entry, notify_targets=[])
    await _change(hass, server, PLUG, "€19.99")
    assert calls == []


async def test_min_drop(hass: HomeAssistant, server, entry) -> None:
    calls = await _setup(hass, entry, min_drop_percent=20)
    await _change(hass, server, PLUG, "€19.99")  # -12%
    assert calls == []


async def test_switch_off(hass: HomeAssistant, server, entry) -> None:
    calls = await _setup(hass, entry)
    switch = _id(hass, "switch", PLUG, "notifications")
    assert hass.states.get(switch).state == "on"
    await hass.services.async_call("switch", "turn_off", {"entity_id": switch}, blocking=True)
    assert hass.states.get(switch).state == "off"
    await _change(hass, server, PLUG, "€19.99")
    assert calls == []


@pytest.mark.parametrize(("target", "expected"), [(20.0, 1), (15.0, 0)])
async def test_target_price(hass: HomeAssistant, server, entry, target, expected) -> None:
    calls = await _setup(hass, entry)
    number = _id(hass, "number", PLUG, "target_price")
    await hass.services.async_call("number", "set_value", {"entity_id": number, "value": target}, blocking=True)
    assert float(hass.states.get(number).state) == target
    await _change(hass, server, PLUG, "€19.99")
    assert len(calls) == expected


async def test_back_in_stock(hass: HomeAssistant, server, entry) -> None:
    calls = await _setup(hass, entry)
    await _change(hass, server, HELMET, "In Stock: False - Price: 319.95")
    assert calls == []  # esaurito: non scelto
    await _change(hass, server, HELMET, "In Stock: True - Price: 319.95", minutes=12, offset=200)
    assert len(calls) == 1
    assert calls[0].data["title"] == "✅ Casco"


async def test_any_change_text(hass: HomeAssistant, server, entry) -> None:
    calls = await _setup(hass, entry, notify_on=["any_change"])
    await _change(hass, server, PAGE, "Secondo articolo")
    assert calls[0].data["message"] == "Secondo articolo"


async def test_cooldown(hass: HomeAssistant, server, entry) -> None:
    calls = await _setup(hass, entry, cooldown_hours=6, notify_on=["price_down", "price_up"])
    await _change(hass, server, PLUG, "€19.99")
    await _change(hass, server, PLUG, "€21.99", minutes=12, offset=200)  # sale: in attesa
    assert len(calls) == 1
    await _change(hass, server, PLUG, "€17.99", minutes=18, offset=300)  # scende sotto l'ultimo avviso: passa
    assert len(calls) == 2


async def test_quiet_hours_queue(hass: HomeAssistant, server, entry) -> None:
    calls = await _setup(hass, entry, quiet_start="00:00:00", quiet_end="23:59:00")
    notifier = entry.runtime_data.notifier
    notifier.now = lambda: dt_util.now().replace(hour=12, minute=0)
    await _change(hass, server, PLUG, "€19.99")
    assert calls == []
    notifier.now = lambda: dt_util.now().replace(hour=23, minute=59, second=30)
    await notifier.async_flush()
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert "19" in calls[0].data["message"]


async def test_test_service(hass: HomeAssistant, server, entry) -> None:
    calls = await _setup(hass, entry)
    await hass.services.async_call(DOMAIN, "test_notification", {}, blocking=True)
    assert len(calls) == 1
    assert "data" not in calls[0].data


async def test_preferences_survive_reload(hass: HomeAssistant, server, entry) -> None:
    await _setup(hass, entry)
    number = _id(hass, "number", PLUG, "target_price")
    await hass.services.async_call("number", "set_value", {"entity_id": number, "value": 18}, blocking=True)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert float(hass.states.get(number).state) == 18
