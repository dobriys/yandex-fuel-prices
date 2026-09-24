"""HTTP client for Yandex Maps organization pages."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

import aiohttp

from .const import ORG_URL
from .parser import StationData, parse_org_id, parse_org_page

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
}
_TIMEOUT = aiohttp.ClientTimeout(total=30)


class CannotConnect(Exception):
    """Network/HTTP error."""


class RegionError(Exception):
    """Yandex redirected away from yandex.ru (request comes from a non-RU IP)."""


class YandexFuelClient:
    """Fetches and parses station pages."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def resolve_org_id(self, text: str) -> str | None:
        """Get org id from an id, a full URL or a short yandex.ru/maps/-/... link."""
        if org_id := parse_org_id(text):
            return org_id
        if "/maps/-/" not in text:
            return None
        url = text if text.startswith("http") else f"https://{text}"
        try:
            async with self._session.get(
                url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=False
            ) as resp:
                return parse_org_id(resp.headers.get("Location", ""))
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect(str(err)) from err

    async def fetch(self, org_id: str) -> StationData:
        """Download the organization page and parse prices."""
        try:
            async with self._session.get(
                ORG_URL.format(org_id=org_id), headers=_HEADERS, timeout=_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                html = await resp.text()
                final_url = str(resp.url)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect(str(err)) from err

        host = urlparse(final_url).hostname or ""
        if "showcaptcha" not in final_url and not host.endswith("yandex.ru"):
            raise RegionError(f"Redirected to {host}")
        return parse_org_page(html, org_id, final_url)
