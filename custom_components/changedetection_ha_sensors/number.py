"""Numero "Prezzo obiettivo" per ogni watch (0 = nessun obiettivo)."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CURRENCY, DEFAULT_CURRENCY
from .coordinator import ChangedetectionConfigEntry, ChangedetectionCoordinator
from .entity import WatchEntity
from .sensor import watch_entities_adder


async def async_setup_entry(
    hass: HomeAssistant, entry: ChangedetectionConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entry.async_on_unload(
        watch_entities_adder(coordinator, async_add_entities, lambda uuid: [TargetPriceNumber(coordinator, uuid)])
    )


class TargetPriceNumber(WatchEntity, NumberEntity):
    """Con un obiettivo, si avvisa solo quando il prezzo e' uguale o sotto."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.MONETARY
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 1_000_000
    _attr_native_step = 0.01

    def __init__(self, coordinator: ChangedetectionCoordinator, uuid: str) -> None:
        super().__init__(coordinator, uuid, "target_price")
        self._attr_native_unit_of_measurement = coordinator.config_entry.options.get(CONF_CURRENCY, DEFAULT_CURRENCY)

    @property
    def native_value(self) -> float:
        return self.coordinator.notifier.target(self.uuid) or 0

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.notifier.set_target(self.uuid, value or None)
        self.async_write_ha_state()
