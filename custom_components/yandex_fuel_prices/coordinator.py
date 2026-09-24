"""Data update coordinator for one station."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, RegionError, YandexFuelClient
from .const import CONF_ORG_ID, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN, DOMAIN
from .parser import CaptchaError, NoPricesError, StationData

_LOGGER = logging.getLogger(__name__)


class StationCoordinator(DataUpdateCoordinator[StationData]):
    """Polls one Yandex Maps organization page.

    On failure the last successful data is kept, so sensors keep the last known price.
    """

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: YandexFuelClient
    ) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.data[CONF_ORG_ID]}",
            update_interval=timedelta(minutes=minutes),
        )
        self.client = client
        self.org_id: str = entry.data[CONF_ORG_ID]

    async def _async_update_data(self) -> StationData:
        try:
            return await self.client.fetch(self.org_id)
        except CaptchaError as err:
            raise UpdateFailed("Yandex returned a captcha, will retry later") from err
        except RegionError as err:
            raise UpdateFailed(
                f"Yandex does not show prices for this IP ({err}); a Russian IP is required"
            ) from err
        except NoPricesError as err:
            raise UpdateFailed(f"No fuel prices on the station page: {err}") from err
        except CannotConnect as err:
            raise UpdateFailed(f"Connection error: {err}") from err
