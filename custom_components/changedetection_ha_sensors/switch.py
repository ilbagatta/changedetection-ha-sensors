"""Interruttore "Notifiche" per ogni watch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ChangedetectionConfigEntry, ChangedetectionCoordinator
from .entity import WatchEntity
from .sensor import watch_entities_adder


async def async_setup_entry(
    hass: HomeAssistant, entry: ChangedetectionConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entry.async_on_unload(
        watch_entities_adder(coordinator, async_add_entities, lambda uuid: [NotificationsSwitch(coordinator, uuid)])
    )


class NotificationsSwitch(WatchEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ChangedetectionCoordinator, uuid: str) -> None:
        super().__init__(coordinator, uuid, "notifications")

    @property
    def is_on(self) -> bool:
        return self.coordinator.notifier.enabled(self.uuid)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.notifier.set_enabled(self.uuid, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.notifier.set_enabled(self.uuid, False)
        self.async_write_ha_state()
