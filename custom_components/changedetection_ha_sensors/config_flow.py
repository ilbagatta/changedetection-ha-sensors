"""Configurazione da interfaccia: indirizzo e chiave API, riautenticazione, riconfigurazione, opzioni."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, ChangedetectionClient, ChangedetectionError, InvalidAuth, normalize_url
from .const import (
    CONF_API_KEY,
    CONF_CURRENCY,
    CONF_EXCLUDED,
    CONF_HISTORY_DEPTH,
    CONF_LIMIT,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_CURRENCY,
    DEFAULT_HISTORY_DEPTH,
    DEFAULT_LIMIT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    INT_OPTIONS,
    LOGGER,
)

PASSWORD = selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))


class ChangedetectionConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> OptionsFlow:
        return ChangedetectionOptionsFlow()

    async def _async_validate(self, url: str, api_key: str, verify_ssl: bool) -> tuple[dict[str, Any], dict[str, str]]:
        """(info del server, errori)."""
        session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)
        client = ChangedetectionClient(session, url, api_key)
        try:
            return await client.async_system_info(), {}
        except InvalidAuth:
            return {}, {"base": "invalid_auth"}
        except CannotConnect:
            return {}, {"base": "cannot_connect"}
        except ChangedetectionError:
            LOGGER.exception("Risposta inattesa da changedetection.io")
            return {}, {"base": "unknown"}

    def _user_schema(self, defaults: Mapping[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_URL, default=defaults.get(CONF_URL, "")): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
                ),
                vol.Required(CONF_API_KEY, default=defaults.get(CONF_API_KEY, "")): PASSWORD,
                vol.Required(CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)): bool,
            }
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            info, errors = await self._async_validate(url, user_input[CONF_API_KEY], user_input[CONF_VERIFY_SSL])
            if not errors:
                LOGGER.debug("changedetection.io %s, %s watch", info.get("version"), info.get("watch_count"))
                return self.async_create_entry(title="Changedetection.io", data={**user_input, CONF_URL: url})
        return self.async_show_form(step_id="user", data_schema=self._user_schema(user_input or {}), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_mismatch(reason="wrong_server")
            _, errors = await self._async_validate(url, user_input[CONF_API_KEY], user_input[CONF_VERIFY_SSL])
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates={**user_input, CONF_URL: url})
        return self.async_show_form(
            step_id="reconfigure", data_schema=self._user_schema(user_input or entry.data), errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            _, errors = await self._async_validate(
                entry.data[CONF_URL], user_input[CONF_API_KEY], entry.data.get(CONF_VERIFY_SSL, True)
            )
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): PASSWORD}),
            description_placeholders={"url": entry.data[CONF_URL]},
            errors=errors,
        )


class ChangedetectionOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            # Il NumberSelector restituisce float: si salvano interi
            data = {**user_input}
            for key in INT_OPTIONS:
                if key in data:
                    data[key] = int(data[key])
            return self.async_create_entry(data=data)

        options = self.config_entry.options
        watches: dict[str, str] = {}
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is not None:
            try:
                raw = await coordinator.client.async_get_watches()
                watches = {uuid: (w.get("title") or w.get("url") or uuid) for uuid, w in raw.items()}
            except ChangedetectionError:
                watches = {uuid: w.title for uuid, w in (coordinator.data or {}).items()}
        # Gli esclusi non sono nei dati del coordinator: restano selezionabili
        for uuid in options.get(CONF_EXCLUDED, []):
            watches.setdefault(uuid, uuid)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=1440, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min"
                    )
                ),
                vol.Required(CONF_LIMIT, default=options.get(CONF_LIMIT, DEFAULT_LIMIT)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=50, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(
                    CONF_HISTORY_DEPTH, default=options.get(CONF_HISTORY_DEPTH, DEFAULT_HISTORY_DEPTH)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=50, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(
                    CONF_CURRENCY, default=options.get(CONF_CURRENCY, DEFAULT_CURRENCY)
                ): selector.TextSelector(),
                vol.Optional(CONF_EXCLUDED, default=options.get(CONF_EXCLUDED, [])): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=uuid, label=title)
                            for uuid, title in sorted(watches.items(), key=lambda kv: kv[1].lower())
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
