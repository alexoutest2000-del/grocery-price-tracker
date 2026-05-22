"""
Flipp flyer API client.
No authentication required — just a random 16-digit session ID.
"""

import random
from typing import Any

import requests

BASE_URL = "https://flyers-ng.flippback.com/api/flipp"

TARGET_STORES = [
    "Maxi",
    "Super C",
    "Metro",
    "IGA",
    "Provigo",
    "Walmart",
    "Adonis",
    "Avril Supermarché Santé",
    "Marché C & T",
    "Costco",
]

GROCERY_CATEGORIES = {"Groceries"}


class FlippClient:
    """Thin wrapper around the Flipp flyer API."""

    def __init__(self, locale: str = "en"):
        self.locale = locale
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (compatible; grocery-price-tracker/0.1)"}
        )

    @staticmethod
    def _generate_sid() -> str:
        return "".join(str(random.randint(0, 9)) for _ in range(16))

    def get_flyers(self, postal_code: str) -> dict[str, Any]:
        """Fetch all flyers for a postal code."""
        url = f"{BASE_URL}/data"
        params = {
            "locale": self.locale,
            "postal_code": postal_code,
            "sid": self._generate_sid(),
        }
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def filter_grocery(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract grocery flyers for target stores only."""
        results = []
        seen = set()
        for flyer in data.get("flyers", []):
            merchant = flyer.get("merchant", "")
            if merchant not in TARGET_STORES:
                continue
            categories = set(flyer.get("categories", []))
            if not categories & GROCERY_CATEGORIES:
                continue
            key = (merchant, flyer.get("valid_from"), flyer.get("valid_to"))
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "id": flyer["id"],
                "merchant": merchant,
                "valid_from": flyer.get("valid_from"),
                "valid_to": flyer.get("valid_to"),
            })
        return results

    def get_flyer_items(self, flyer_id: int) -> list[dict[str, Any]]:
        """Fetch all items for a specific flyer."""
        url = f"{BASE_URL}/flyers/{flyer_id}/flyer_items"
        params = {"locale": self.locale, "sid": self._generate_sid()}
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_all_items(self, postal_code: str) -> list[dict[str, Any]]:
        """Convenience: get all items across all target store flyers."""
        data = self.get_flyers(postal_code)
        flyers = self.filter_grocery(data)
        all_items = []
        for flyer in flyers:
            items = self.get_flyer_items(flyer["id"])
            for item in items:
                item["_merchant"] = flyer["merchant"]
                item["_flyer_id"] = flyer["id"]
            all_items.extend(items)
        return all_items
