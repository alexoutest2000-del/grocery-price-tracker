"""
Database models for the grocery price tracker.
"""
import datetime as dt
import json
import os
import sqlite3

DB_PATH = os.environ.get("GPTRACKER_DB", "data/prices.db")


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            flyer_merchant_name TEXT NOT NULL,
            address TEXT,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS price_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_name TEXT NOT NULL,
            flyer_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            brand TEXT,
            price TEXT,
            unit_price REAL,
            size_raw TEXT,
            image_url TEXT,
            valid_from TEXT NOT NULL,
            valid_to TEXT NOT NULL,
            scraped_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(flyer_id, product_name, store_name)
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_store
            ON price_snapshots(store_name);
        CREATE INDEX IF NOT EXISTS idx_snapshots_product
            ON price_snapshots(product_name);
        CREATE INDEX IF NOT EXISTS idx_snapshots_valid
            ON price_snapshots(valid_from, valid_to);
    """)
    conn.commit()
    conn.close()


def insert_snapshot(item: dict) -> bool:
    """Insert a flyer item into the database. Returns True if inserted."""
    conn = get_conn()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO price_snapshots
                (store_name, flyer_id, product_name, brand, price, image_url,
                 valid_from, valid_to, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["_merchant"],
            item["_flyer_id"],
            item.get("name", ""),
            item.get("brand"),
            item.get("price"),
            item.get("cutout_image_url"),
            item.get("valid_from", dt.datetime.now(dt.timezone.utc).isoformat()),
            item.get("valid_to", dt.datetime.now(dt.timezone.utc).isoformat()),
            dt.datetime.now(dt.timezone.utc).isoformat(),
        ))
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def search_items(query: str, limit: int = 50) -> list[dict]:
    """Search products across all stores, ordered by price."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT store_name, product_name, brand, price, image_url, valid_from, valid_to
            FROM price_snapshots
            WHERE product_name LIKE ?
            ORDER BY CAST(price AS REAL) ASC
            LIMIT ?
        """, (f"%{query}%", limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def export_json(
    output_path: str | None = None, only_current: bool = True
) -> str:
    """Export all products to a JSON file for the static dashboard.

    Returns the path written.
    """
    out = output_path or os.path.join(os.path.dirname(DB_PATH), "prices.json")
    conn = get_conn()
    try:
        if only_current:
            today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
            rows = conn.execute(
                """SELECT store_name, product_name, brand, price, size_raw,
                          image_url, valid_from, valid_to, scraped_at
                   FROM price_snapshots
                   WHERE valid_to >= ?
                   ORDER BY store_name, CAST(price AS REAL) ASC""",
                (today,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT store_name, product_name, brand, price, size_raw,
                          image_url, valid_from, valid_to, scraped_at
                   FROM price_snapshots
                   ORDER BY store_name, CAST(price AS REAL) ASC"""
            ).fetchall()

        items = []
        for r in rows:
            d = dict(r)
            # Convert price to float for easier JS sorting
            try:
                d["price_num"] = float(d["price"]) if d["price"] else 0.0
            except (ValueError, TypeError):
                d["price_num"] = 0.0
            items.append(d)

        total_stores = conn.execute(
            "SELECT COUNT(DISTINCT store_name) FROM price_snapshots"
        ).fetchone()[0]

        result = {
            "last_updated": dt.datetime.now(dt.timezone.utc).isoformat(),
            "total_items": len(items),
            "total_stores": total_stores,
            "items": items,
        }

        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return out
    finally:
        conn.close()
