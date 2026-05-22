"""
Daily orchestrator: fetch all flyers, insert into DB, report stats.
Run via: python -m scrapers.run_all
"""

import sys
from datetime import datetime, timezone

from db.models import init_db, insert_snapshot, get_conn, export_json
from scrapers.flipp_client import FlippClient

POSTAL_CODE = "J3Y6J8"  # Metro Plus Riendeau, Saint-Hubert


def main() -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting daily scrape...")
    init_db()

    client = FlippClient()
    data = client.get_flyers(POSTAL_CODE)
    flyers = client.filter_grocery(data)

    print(f"Found {len(flyers)} grocery flyers:")
    for f in flyers:
        print(f"  - {f['merchant']} (flyer #{f['id']})")

    total_items = 0
    new_items = 0
    store_counts: dict[str, int] = {}

    for flyer in flyers:
        try:
            items = client.get_flyer_items(flyer["id"])
        except Exception as e:
            print(f"  ⚠ Failed to fetch {flyer['merchant']}: {e}", file=sys.stderr)
            continue

        for item in items:
            item["_merchant"] = flyer["merchant"]
            item["_flyer_id"] = flyer["id"]
            if insert_snapshot(item):
                new_items += 1
            total_items += 1

        store_counts[flyer["merchant"]] = len(items)
        print(f"  ✓ {flyer['merchant']}: {len(items)} items")

    print(f"\nDone. {total_items} items ({new_items} new) across {len(store_counts)} stores.")

    # Show store breakdown
    for store, count in sorted(store_counts.items()):
        print(f"  {store}: {count}")

    # Show sample of what we got
    conn = get_conn()
    try:
        total_db = conn.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0]
        stores_db = conn.execute(
            "SELECT COUNT(DISTINCT store_name) FROM price_snapshots"
        ).fetchone()[0]
        print(f"\nDatabase now has {total_db} items across {stores_db} stores.")

        # Export JSON for static dashboard
        json_path = export_json()
        print(f"  ✓ Exported dashboard data to {json_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
