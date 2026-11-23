"""Sensori: prezzo e ultima modifica di ogni watch, riepilogo delle ultime modifiche."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CURRENCY, CONF_LIMIT, DEFAULT_CURRENCY, int_option
from .coordinator import ChangedetectionConfigEntry, ChangedetectionCoordinator
from .entity import ServerEntity, WatchEntity


def watch_entities_adder(
    coordinator: ChangedetectionCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[str], list[Any]],
) -> Callable[[], None]:
    """Aggiunge le entita' dei watch nuovi a ogni aggiornamento."""
    known: set[str] = set()

    @callback
    def add_new() -> None:
        new = [uuid for uuid in coordinator.data or {} if uuid not in known]
        known.update(new)
        entities = [entity for uuid in new for entity in factory(uuid)]
        if entities:
            async_add_entities(entities)

    add_new()
    return coordinator.async_add_listener(add_new)


async def async_setup_entry(
    hass: HomeAssistant, entry: ChangedetectionConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([RecentChangesSensor(coordinator), WatchCountSensor(coordinator)])
    entry.async_on_unload(
        watch_entities_adder(
            coordinator,
            async_add_entities,
            lambda uuid: [PriceSensor(coordinator, uuid), LastChangedSensor(coordinator, uuid)],
        )
    )


class PriceSensor(WatchEntity, SensorEntity):
    """Prezzo letto dall'ultima rilevazione (sconosciuto se la pagina non contiene un prezzo)."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: ChangedetectionCoordinator, uuid: str) -> None:
        super().__init__(coordinator, uuid, "price")
        self._attr_native_unit_of_measurement = coordinator.config_entry.options.get(CONF_CURRENCY, DEFAULT_CURRENCY)

    @property
    def native_value(self) -> float | None:
        return self.watch.price if self.watch else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        watch = self.watch
        if watch is None:
            return {}
        return {
            "previous_price": watch.old_price,
            "trend": watch.trend,
            "in_stock": watch.in_stock,
            "url": watch.url,
        }


class LastChangedSensor(WatchEntity, SensorEntity):
    """Quando la pagina e' cambiata l'ultima volta; negli attributi il testo rilevato."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: ChangedetectionCoordinator, uuid: str) -> None:
        super().__init__(coordinator, uuid, "last_changed")

    @property
    def native_value(self) -> datetime | None:
        return self.watch.last_changed if self.watch else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        watch = self.watch
        if watch is None:
            return {}
        return {
            "text": watch.text[:255],
            "url": watch.url,
            "uuid": watch.uuid,
            "last_checked": watch.last_checked,
            "viewed": watch.viewed,
            "paused": watch.paused,
            "error": watch.error,
        }


class RecentChangesSensor(ServerEntity, SensorEntity):
    """Stato: ora dell'ultima modifica. Attributo `watches`: le ultime N modifiche, usato dalla card."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    # La lista cambia spesso e puo' essere lunga: fuori dal registro storico
    _unrecorded_attributes = frozenset({"watches"})

    def __init__(self, coordinator: ChangedetectionCoordinator) -> None:
        super().__init__(coordinator, "recent_changes")

    @property
    def native_value(self) -> datetime | None:
        recent = self.coordinator.recent(1)
        return recent[0].last_changed if recent else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        limit = int_option(self.coordinator.config_entry.options, CONF_LIMIT)
        currency = self.coordinator.config_entry.options.get(CONF_CURRENCY, DEFAULT_CURRENCY)
        watches = []
        for watch in self.coordinator.recent(limit):
            item = watch.as_dict()
            item["text"] = watch.text[:200]
            watches.append(item)
        return {"changedetection_card": True, "currency": currency, "watches": watches}


class WatchCountSensor(ServerEntity, SensorEntity):
    """Numero di watch seguiti (esclusi quelli tolti nelle opzioni)."""

    _attr_native_unit_of_measurement = "watch"

    def __init__(self, coordinator: ChangedetectionCoordinator) -> None:
        super().__init__(coordinator, "watch_count")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = (self.coordinator.data or {}).values()
        return {
            "with_errors": sum(1 for w in data if w.error),
            "paused": sum(1 for w in data if w.paused),
            "unviewed": sum(1 for w in data if not w.viewed),
        }
