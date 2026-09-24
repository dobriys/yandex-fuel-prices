"""Constants for the Yandex Fuel Prices integration."""

from datetime import timedelta

DOMAIN = "yandex_fuel_prices"

CONF_STATION = "station"
CONF_ORG_ID = "org_id"
CONF_FUEL = "fuel"
CONF_NAME = "name"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_FUEL = "Пропан"
DEFAULT_SCAN_INTERVAL_MIN = 180
MIN_SCAN_INTERVAL_MIN = 30

ORG_URL = "https://yandex.ru/maps/org/{org_id}/"

UNIT_RUB_PER_LITER = "₽/л"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MIN)
