"""Yandex Fuel Prices: fuel prices of gas stations from Yandex Maps (Yandex.Zapravki data)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import YandexFuelClient
from .coordinator import StationCoordinator

PLATFORMS = [Platform.SENSOR]

type YandexFuelConfigEntry = ConfigEntry[StationCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: YandexFuelConfigEntry) -> bool:
    """Set up a station from a config entry."""
    # Own session per entry (own cookie jar); HA closes it when this entry unloads/reloads,
    # so it must not be shared between entries.
    client = YandexFuelClient(async_create_clientsession(hass))
    coordinator = StationCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: YandexFuelConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: YandexFuelConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
