"""Tests for the Flipp API client."""

import pytest

from scrapers.flipp_client import TARGET_STORES, FlippClient


def test_generate_sid():
    sid = FlippClient._generate_sid()
    assert len(sid) == 16
    assert sid.isdigit()


def test_filter_grocery_filters_out_non_target():
    client = FlippClient()
    data = {
        "flyers": [
            {"id": 1, "merchant": "Canadian Tire", "categories": ["Groceries"]},
            {"id": 2, "merchant": "Best Buy", "categories": ["All Flyers"]},
        ]
    }
    result = client.filter_grocery(data)
    assert len(result) == 0


def test_filter_grocery_keeps_target():
    client = FlippClient()
    data = {
        "flyers": [
            {
                "id": 100,
                "merchant": "Maxi",
                "categories": ["Groceries"],
                "valid_from": "2026-05-21",
                "valid_to": "2026-05-27",
            },
            {
                "id": 200,
                "merchant": "Best Buy",
                "categories": ["Electronics"],
                "valid_from": "2026-05-21",
                "valid_to": "2026-05-27",
            },
        ]
    }
    result = client.filter_grocery(data)
    assert len(result) == 1
    assert result[0]["merchant"] == "Maxi"
    assert result[0]["id"] == 100


def test_filter_grocery_deduplicates():
    client = FlippClient()
    data = {
        "flyers": [
            {
                "id": 1,
                "merchant": "Maxi",
                "categories": ["Groceries"],
                "valid_from": "2026-05-21",
                "valid_to": "2026-05-27",
            },
            {
                "id": 2,
                "merchant": "Maxi",
                "categories": ["Groceries"],
                "valid_from": "2026-05-21",
                "valid_to": "2026-05-27",
            },
        ]
    }
    result = client.filter_grocery(data)
    assert len(result) == 1


def test_filter_grocery_filters_non_grocery_categories():
    client = FlippClient()
    data = {
        "flyers": [
            {
                "id": 1,
                "merchant": "Walmart",
                "categories": ["Home & Garden"],
                "valid_from": "2026-05-21",
                "valid_to": "2026-06-03",
            },
        ]
    }
    result = client.filter_grocery(data)
    assert len(result) == 0


def test_all_target_stores_are_strings():
    for store in TARGET_STORES:
        assert isinstance(store, str)
        assert len(store) > 0


@pytest.mark.slow
def test_live_api_smoke():
    """Verify the Flipp API is reachable and returns grocery flyers for Saint-Hubert."""
    client = FlippClient()
    data = client.get_flyers("J3Y6J8")
    assert "flyers" in data
    flyers = client.filter_grocery(data)
    assert len(flyers) >= 5, f"Expected >=5 grocery flyers, got {len(flyers)}"

    # Grab a flyer and check items
    items = client.get_flyer_items(flyers[0]["id"])
    assert len(items) > 0
    assert "name" in items[0]
    assert "price" in items[0]
