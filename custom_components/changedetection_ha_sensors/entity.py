"""Entita' base: un dispositivo per il server e uno per ogni watch."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_URL, DOMAIN
from .coordinator import ChangedetectionCoordinator, Watch


def server_device(coordinator: ChangedetectionCoordinator) -> DeviceInfo:
    entry = coordinator.config_entry
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Changedetection.io",
        manufacturer="changedetection.io",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=entry.data[CONF_URL],
    )


class ServerEntity(CoordinatorEntity[ChangedetectionCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ChangedetectionCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = server_device(coordinator)


class WatchEntity(CoordinatorEntity[ChangedetectionCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ChangedetectionCoordinator, uuid: str, key: str) -> None:
        super().__init__(coordinator)
        self.uuid = uuid
        self._attr_translation_key = key
        self._attr_unique_id = f"{uuid}_{key}"
        watch = coordinator.data[uuid]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uuid)},
            name=watch.title,
            manufacturer="changedetection.io",
            model="Watch",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"{coordinator.config_entry.data[CONF_URL]}/edit/{uuid}",
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
        )

    @property
    def watch(self) -> Watch | None:
        return (self.coordinator.data or {}).get(self.uuid)

    @property
    def available(self) -> bool:
        return super().available and self.watch is not None
