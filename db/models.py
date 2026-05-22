"""
Database models for the grocery price tracker.
"""
import datetime as dt
import json
import os
import re
import sqlite3

DB_PATH = os.environ.get("GPTRACKER_DB", "data/prices.db")

# ── Size extraction regex ──────────────────────────────────────────
_SIZE_RE = re.compile(r"(\d+[\.,]?\d*)\s*(G|KG|LB|L|ML|OZ)", re.IGNORECASE)

# Unit conversion factors → grams or mL
_TO_GRAMS = {"G": 1, "KG": 1000, "LB": 453.6, "OZ": 28.35}
_TO_ML = {"L": 1000, "ML": 1}


def _compute_unit_price(price_num: float, size_raw: str | None) -> dict | None:
    """Normalize to $/100g or $/100mL. Returns {value, label} or None."""
    if not price_num or price_num <= 0 or not size_raw:
        return None
    m = _SIZE_RE.search(size_raw.upper().replace(",", "."))
    if not m:
        return None
    try:
        qty = float(m.group(1))
        unit = m.group(2).upper()
    except ValueError:
        return None
    if qty <= 0:
        return None
    if unit in _TO_GRAMS:
        grams = qty * _TO_GRAMS[unit]
        return {"value": round(price_num / (grams / 100), 2), "label": "100g"}
    if unit in _TO_ML:
        ml = qty * _TO_ML[unit]
        return {"value": round(price_num / (ml / 100), 2), "label": "100mL"}
    return None


def _clean_display(raw: str) -> str:
    """Extract a readable English display name from a bilingual raw string."""
    if not raw:
        return "Unknown"
    parts = raw.split("|")
    name = parts[1].strip() if len(parts) > 1 else parts[0].strip()
    # Strip trailing size/punctuation noise
    name = re.sub(r",\s*\d+[\.,]?\d*\s*(G|KG|LB|L|ML|OZ)\s*$", "", name, flags=re.IGNORECASE)
    name = name.strip().strip(",").strip()
    if not name:
        name = parts[0].strip()
    return name.title() if name.isupper() else name


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
                (store_name, flyer_id, product_name, brand, price, size_raw,
                 image_url, valid_from, valid_to, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["_merchant"],
            item["_flyer_id"],
            item.get("name", ""),
            item.get("brand"),
            item.get("price"),
            item.get("size"),
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
            # Price as float
            try:
                d["price_num"] = float(d["price"]) if d["price"] else 0.0
            except (ValueError, TypeError):
                d["price_num"] = 0.0
            # Clean display name
            d["display_name"] = _clean_display(d.get("product_name", ""))
            # Unit price
            up = _compute_unit_price(d["price_num"], d.get("size_raw"))
            d["unit_price"] = up["value"] if up else None
            d["unit_label"] = up["label"] if up else None
            # Sale end date for expiry countdown
            d["days_left"] = None
            if d.get("valid_to"):
                try:
                    end = dt.datetime.strptime(d["valid_to"][:10], "%Y-%m-%d").date()
                    d["days_left"] = (end - dt.datetime.now(dt.timezone.utc).date()).days
                except (ValueError, TypeError):
                    pass
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
