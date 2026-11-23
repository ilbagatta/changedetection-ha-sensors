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
    CONF_COOLDOWN_HOURS,
    CONF_CURRENCY,
    CONF_EXCLUDED,
    CONF_HISTORY_DEPTH,
    CONF_MIN_DROP_AMOUNT,
    CONF_MIN_DROP_PERCENT,
    CONF_NOTIFY_ON,
    CONF_NOTIFY_TARGETS,
    CONF_QUIET_END,
    CONF_QUIET_START,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_COOLDOWN_HOURS,
    DEFAULT_CURRENCY,
    DEFAULT_HISTORY_DEPTH,
    DEFAULT_NOTIFY_ON,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    INT_OPTIONS,
    LOGGER,
    NOTIFY_KINDS,
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
    """Menu: opzioni generali, notifiche. Ogni pagina salva solo i suoi campi e conserva gli altri."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["general", "notifications"])

    def _save(self, user_input: dict[str, Any], drop: tuple[str, ...] = ()) -> ConfigFlowResult:
        data = {k: v for k, v in self.config_entry.options.items() if k not in drop}
        data.update(user_input)
        # Il NumberSelector restituisce float: si salvano interi
        for key in INT_OPTIONS:
            if key in data:
                data[key] = int(data[key])
        data.pop("limit", None)  # opzione della 0.1.x
        return self.async_create_entry(data=data)

    async def async_step_general(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(user_input)

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
        return self.async_show_form(step_id="general", data_schema=schema)

    async def async_step_notifications(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            # Ore di silenzio lasciate vuote: si tolgono
            return self._save(user_input, drop=(CONF_QUIET_START, CONF_QUIET_END))

        options = self.config_entry.options
        services = sorted(
            f"notify.{name}"
            for name in self.hass.services.async_services_for_domain("notify")
            if name != "send_message"
        )
        for target in options.get(CONF_NOTIFY_TARGETS, []):  # anche se il servizio non c'e' piu'
            if target not in services:
                services.append(target)

        def quiet(key: str) -> vol.Optional:
            value = options.get(key)
            return vol.Optional(key, description={"suggested_value": value} if value else None)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NOTIFY_TARGETS, default=options.get(CONF_NOTIFY_TARGETS, [])
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=services, multiple=True, mode=selector.SelectSelectorMode.DROPDOWN, custom_value=True
                    )
                ),
                vol.Required(
                    CONF_NOTIFY_ON, default=options.get(CONF_NOTIFY_ON, DEFAULT_NOTIFY_ON)
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=NOTIFY_KINDS,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key=CONF_NOTIFY_ON,
                    )
                ),
                vol.Required(
                    CONF_MIN_DROP_PERCENT, default=options.get(CONF_MIN_DROP_PERCENT, 0)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=100, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="%"
                    )
                ),
                vol.Required(
                    CONF_MIN_DROP_AMOUNT, default=options.get(CONF_MIN_DROP_AMOUNT, 0)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100000,
                        step=0.01,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement=options.get(CONF_CURRENCY, DEFAULT_CURRENCY),
                    )
                ),
                vol.Required(
                    CONF_COOLDOWN_HOURS, default=options.get(CONF_COOLDOWN_HOURS, DEFAULT_COOLDOWN_HOURS)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=168, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="h"
                    )
                ),
                quiet(CONF_QUIET_START): selector.TimeSelector(),
                quiet(CONF_QUIET_END): selector.TimeSelector(),
            }
        )
        return self.async_show_form(step_id="notifications", data_schema=schema)
