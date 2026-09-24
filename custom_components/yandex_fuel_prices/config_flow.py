"""Config flow for Yandex Fuel Prices."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, RegionError, YandexFuelClient
from .const import (
    CONF_FUEL,
    CONF_NAME,
    CONF_ORG_ID,
    CONF_SCAN_INTERVAL,
    CONF_STATION,
    DEFAULT_FUEL,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    MIN_SCAN_INTERVAL_MIN,
)
from .parser import CaptchaError, NoPricesError, normalize_fuel


class YandexFuelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a station by Yandex Maps link or organization id."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"fuels": "-"}

        if user_input is not None:
            client = YandexFuelClient(async_get_clientsession(self.hass))
            fuel = user_input[CONF_FUEL].strip()
            try:
                org_id = await client.resolve_org_id(user_input[CONF_STATION])
                if org_id is None:
                    errors[CONF_STATION] = "invalid_station"
                else:
                    data = await client.fetch(org_id)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except RegionError:
                errors["base"] = "region"
            except CaptchaError:
                errors["base"] = "captcha"
            except NoPricesError:
                errors["base"] = "no_prices"

            if not errors:
                found = data.find_price(fuel)
                if found is None:
                    errors[CONF_FUEL] = "fuel_not_found"
                    placeholders["fuels"] = ", ".join(data.prices)
                else:
                    # Store the fuel as typed: Yandex spells it differently per station
                    # ("Пропан" / "ПРОПАН"), matching is case-insensitive anyway.
                    await self.async_set_unique_id(f"{org_id}_{normalize_fuel(fuel)}")
                    self._abort_if_unique_id_configured()
                    name = (user_input.get(CONF_NAME) or "").strip() or data.title or org_id
                    return self.async_create_entry(
                        title=f"{name} — {fuel}",
                        data={CONF_ORG_ID: org_id, CONF_FUEL: fuel, CONF_NAME: name},
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION): str,
                vol.Required(CONF_FUEL, default=DEFAULT_FUEL): str,
                vol.Optional(CONF_NAME): str,
            }
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return YandexFuelOptionsFlow()


class YandexFuelOptionsFlow(OptionsFlow):
    """Polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_MIN, max=1440)
                    )
                }
            ),
        )
