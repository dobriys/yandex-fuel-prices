"""Sensors: fuel price and price update time for a station."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import YandexFuelConfigEntry
from .const import CONF_FUEL, CONF_NAME, DOMAIN, ORG_URL, UNIT_RUB_PER_LITER
from .coordinator import StationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YandexFuelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [FuelPriceSensor(coordinator, entry), PriceUpdatedSensor(coordinator, entry)]
    )


class _StationEntity(CoordinatorEntity[StationCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: StationCoordinator, entry: YandexFuelConfigEntry) -> None:
        super().__init__(coordinator)
        self._fuel: str = entry.data[CONF_FUEL]
        org_id = coordinator.org_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, org_id)},
            name=entry.data.get(CONF_NAME) or org_id,
            manufacturer="Яндекс Карты",
            model="АЗС / АГЗС",
            configuration_url=ORG_URL.format(org_id=org_id),
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        # Keep the last known price during temporary failures (captcha, network).
        return self.coordinator.data is not None


class FuelPriceSensor(_StationEntity, SensorEntity):
    """Price of the selected fuel."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UNIT_RUB_PER_LITER
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:gas-cylinder"

    def __init__(self, coordinator: StationCoordinator, entry: YandexFuelConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = self._fuel
        self._attr_unique_id = entry.unique_id

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.find_price(self._fuel) is not None

    @property
    def native_value(self) -> float | None:
        found = self.coordinator.data.find_price(self._fuel)
        return found[1] if found else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        attrs: dict[str, Any] = {
            "fuel_name": self._fuel,
            "station": self.device_info.get("name") if self.device_info else None,
            "address": data.address,
            "price_updated": data.updated.isoformat() if data.updated else None,
            "source": data.source,
            "all_prices": data.prices,
            "last_fetch_ok": self.coordinator.last_update_success,
            "yandex_org_id": data.org_id,
        }
        if data.latitude is not None and data.longitude is not None:
            attrs[ATTR_LATITUDE] = data.latitude
            attrs[ATTR_LONGITUDE] = data.longitude
        return attrs


class PriceUpdatedSensor(_StationEntity, SensorEntity):
    """When Yandex.Zapravki last updated the prices of this station."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "price_updated"

    def __init__(self, coordinator: StationCoordinator, entry: YandexFuelConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.unique_id}_updated"

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.data.updated
