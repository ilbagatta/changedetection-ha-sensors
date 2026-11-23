"""Pulsanti: ricontrolla un watch, ricontrolla tutti."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import ChangedetectionError
from .coordinator import ChangedetectionConfigEntry
from .entity import ServerEntity, WatchEntity
from .sensor import watch_entities_adder


async def async_setup_entry(
    hass: HomeAssistant, entry: ChangedetectionConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([RecheckAllButton(coordinator, "recheck_all")])
    entry.async_on_unload(
        watch_entities_adder(
            coordinator, async_add_entities, lambda uuid: [RecheckButton(coordinator, uuid, "recheck")]
        )
    )


class RecheckButton(WatchEntity, ButtonEntity):
    async def async_press(self) -> None:
        try:
            await self.coordinator.client.async_recheck(self.uuid)
        except ChangedetectionError as err:
            raise HomeAssistantError(f"Ricontrollo non avviato: {err}") from err


class RecheckAllButton(ServerEntity, ButtonEntity):
    async def async_press(self) -> None:
        try:
            await self.coordinator.client.async_recheck_all()
        except ChangedetectionError as err:
            raise HomeAssistantError(f"Ricontrollo non avviato: {err}") from err
