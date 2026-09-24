"""Pure parsing helpers for Yandex Maps organization pages (no HA/aiohttp imports)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import re
from typing import Any

_STATE_RE = re.compile(
    r'<script[^>]*class="state-view"[^>]*>(.*?)</script>', re.DOTALL
)
_ORG_ID_RE = re.compile(r"/org/(?:[^/?#]+/)?(\d{5,})")
_CAPTCHA_MARKERS = ("showcaptcha", "checkcaptcha", "SmartCaptcha")


class ParseError(Exception):
    """Base parsing error."""


class CaptchaError(ParseError):
    """Yandex returned a captcha page instead of the organization page."""


class NoPricesError(ParseError):
    """The page has no fuelInfo block (no prices, or request came from a non-RU IP)."""


@dataclass
class StationData:
    """Fuel prices of one station."""

    org_id: str
    title: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    updated: datetime | None = None
    source: str | None = None
    prices: dict[str, float] = field(default_factory=dict)

    def find_price(self, fuel: str) -> tuple[str, float] | None:
        """Return (name, price) for a fuel, case-insensitive; exact match first, then substring."""
        wanted = normalize_fuel(fuel)
        for name, price in self.prices.items():
            if normalize_fuel(name) == wanted:
                return name, price
        for name, price in self.prices.items():
            if wanted in normalize_fuel(name):
                return name, price
        return None


def normalize_fuel(name: str) -> str:
    """Normalize a fuel name for comparison."""
    return " ".join(name.casefold().replace("ё", "е").split())


def parse_org_id(text: str) -> str | None:
    """Extract an organization id from a Yandex Maps URL or a bare id."""
    text = text.strip()
    if text.isdigit() and len(text) >= 5:
        return text
    if match := _ORG_ID_RE.search(text):
        return match.group(1)
    if match := re.search(r"oid(?:%3D|=)(\d{5,})", text):
        return match.group(1)
    return None


def is_captcha(html: str, url: str = "") -> bool:
    """Detect a Yandex captcha page."""
    if "showcaptcha" in url:
        return True
    return "state-view" not in html and any(m in html for m in _CAPTCHA_MARKERS)


def _find_item(node: Any, org_id: str) -> dict | None:
    """Depth-first search for the organization object with the given id."""
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if "fuelInfo" in cur and str(cur.get("id")) == org_id:
                return cur
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def _extract_fuel_info_raw(html: str) -> dict | None:
    """Fallback: decode the first "fuelInfo" object directly from the HTML."""
    idx = html.find('"fuelInfo":')
    if idx < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(html, idx + len('"fuelInfo":'))
    except ValueError:
        return None
    return {"fuelInfo": obj}


def parse_org_page(html: str, org_id: str, url: str = "") -> StationData:
    """Parse fuel prices from a Yandex Maps organization page."""
    if is_captcha(html, url):
        raise CaptchaError("Yandex returned a captcha")

    item: dict | None = None
    state = None
    if match := _STATE_RE.search(html):
        try:
            state = json.loads(match.group(1))
        except ValueError:
            state = None
    if state is not None:
        # Only trust the object with our id: the page may also contain nearby stations.
        item = _find_item(state, org_id)
    else:
        item = _extract_fuel_info_raw(html)
    if item is None or not item.get("fuelInfo"):
        raise NoPricesError("No fuelInfo on the page")

    info = item["fuelInfo"]
    data = StationData(org_id=org_id)
    data.title = item.get("title") or item.get("shortTitle")
    data.address = item.get("fullAddress") or item.get("address")
    coords = item.get("coordinates")
    if isinstance(coords, list) and len(coords) == 2:
        data.longitude, data.latitude = float(coords[0]), float(coords[1])
    if ts := info.get("timestamp"):
        data.updated = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    data.source = (info.get("source") or {}).get("name")
    for fuel in info.get("items") or []:
        name = fuel.get("name")
        value = (fuel.get("price") or {}).get("value")
        if name and isinstance(value, (int, float)):
            data.prices[name] = float(value)
    if not data.prices:
        raise NoPricesError("fuelInfo has no prices")
    return data
