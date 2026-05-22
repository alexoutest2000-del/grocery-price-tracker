# 🛒 Grocery Price Tracker — Build Plan for Hermes AI

## 1. Project Summary

**What:** A daily automated price comparison system for grocery stores in Saint-Hubert, Québec, Canada.

**Why:** Alex wants to search for any grocery item (e.g., "milk," "chicken breast," "Coke") and instantly see which store has it cheapest — with prices, product images, and store names side by side.

**How:** Instead of scraping 10 different grocery websites (slow, fragile, anti-bot defenses), the system taps into the **Flipp flyer API** — a single, unauthenticated API that aggregates weekly flyers from virtually all major Canadian grocery chains. One endpoint, one source, all stores.

---

## 2. Stores to Track

These are the grocery stores in and around Saint-Hubert, QC (postal code: J3Y 6J8). All publish weekly flyers on Flipp:

| # | Store | Type |
|---|-------|------|
| 1 | Maxi | Discount supermarket (Loblaw) |
| 2 | Super C | Discount supermarket (Metro) |
| 3 | Metro | Mid-range supermarket |
| 4 | IGA | Mid-range supermarket (Sobeys) |
| 5 | Provigo | Mid-range supermarket (Loblaw) |
| 6 | Walmart | Hypermarket (groceries only) |
| 7 | Adonis | Mediterranean/specialty |
| 8 | Avril Supermarché Santé | Health/organic |
| 9 | Marché C & T | Asian supermarket |
| 10 | Costco | Warehouse club |

---

## 3. Technical Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     GitHub Actions (CI/CD)                        │
│                                                                   │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐  │
│  │ CI Pipeline  │    │ Daily Scrape      │    │ Data Auto-Commit│  │
│  │ (lint+test)  │    │ (6 AM ET / 10 UTC)│    │ (git push data/)│  │
│  └─────────────┘    └────────┬─────────┘    └────────┬────────┘  │
│                              │                        │           │
└──────────────────────────────┼────────────────────────┼───────────┘
                               │                        │
                               ▼                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Python Application                         │
│                                                                   │
│  ┌────────────────┐   ┌───────────────┐   ┌──────────────────┐  │
│  │ Flipp API      │──▶│ Database       │──▶│ Fuzzy Matcher    │  │
│  │ Client         │   │ (SQLite)       │   │ (product grouping)│  │
│  │ (scrapers/)    │   │ (db/)          │   │ (matcher/)       │  │
│  └────────────────┘   └───────────────┘   └──────────────────┘  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Data Layer                                  │
│                                                                   │
│  data/prices.db   ← version-controlled SQLite database            │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ price_snapshots                                              │ │
│  │  - store_name, flyer_id                                      │ │
│  │  - product_name (raw, bilingual)                             │ │
│  │  - brand, price, unit_price                                  │ │
│  │  - image_url (high-res product photo)                        │ │
│  │  - valid_from, valid_to (sale dates)                         │ │
│  │  - scraped_at (when we captured it)                          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  stores                                                           │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ name, flyer_merchant_name, address, active                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. The Flipp API (Your Single Data Source)

This is the critical piece. Flipp is a Canadian flyer aggregator. Their web app calls an internal API that requires **no authentication** — just a random 16-digit session ID.

### 4.1 Base URL
```
https://flyers-ng.flippback.com/api/flipp
```

### 4.2 Endpoint: Get Flyers by Postal Code
```
GET /data?locale=en&postal_code=J3Y6J8&sid=1234567890123456
```

**Response structure** (relevant fields):
```json
{
  "flyers": [
    {
      "id": 1234567,
      "merchant": "Maxi",
      "valid_from": "2026-05-21",
      "valid_to": "2026-05-27",
      "categories": ["Groceries", "Dairy"],
      "postal_code": "J3Y6J8"
    }
  ]
}
```

### 4.3 Endpoint: Get Items for a Flyer
```
GET /flyers/{flyer_id}/flyer_items?locale=en&sid=1234567890123456
```

**Response** (array of items):
```json
[
  {
    "id": 99887766,
    "name": "LAIT 2% 4L | 2% MILK 4L",
    "brand": "Québon",
    "price": "6.49",
    "cutout_image_url": "https://dam.flippenterprise.net/.../cutout.jpg",
    "valid_from": "2026-05-21",
    "valid_to": "2026-05-27",
    "size": "4 L"
  }
]
```

### 4.4 Key Details
- **No API key or auth required** — just a 16-digit numeric `sid` parameter (any random digits work)
- **Rate limiting:** Be respectful. 30-60s between runs is fine. Don't hammer it.
- **Locale:** `en` or `fr` — picking `en` gives English product names where available. Names are bilingual (French | English split by `|`)
- **Postal code:** `J3Y6J8` is the Metro Plus Riendeau on Cousineau in Saint-Hubert. This covers the area.
- **Categories:** Filter flyers to `"Groceries"` category. Ignore flyers tagged only as `"Electronics"`, `"Clothing"`, etc.

---

## 5. Component Specifications

### 5.1 Flipp API Client (`scrapers/flipp_client.py`)

**Class: `FlippClient`**

```python
class FlippClient:
    def __init__(self, locale: str = "en")
    def get_flyers(postal_code: str) -> dict           # Raw API response
    def filter_grocery(data: dict) -> list[dict]       # Filter to target stores + Groceries category
    def get_flyer_items(flyer_id: int) -> list[dict]   # Items in a specific flyer
    def get_all_items(postal_code: str) -> list[dict]   # Convenience: all items across all stores
```

**Requirements:**
- Uses `requests.Session()` with a descriptive User-Agent
- Random 16-digit `sid` per call (no persistence needed)
- 30-second timeout on HTTP calls
- `filter_grocery()` must:
  - Only return flyers where `merchant` is in the 10 target stores
  - Only return flyers with `"Groceries"` in their categories
  - Deduplicate on `(merchant, valid_from, valid_to)` — some stores have overlapping flyers

### 5.2 Database (`db/models.py`)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS price_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name TEXT NOT NULL,
    flyer_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,        -- Raw bilingual name from API
    brand TEXT,                        -- Extracted brand (nullable)
    price TEXT,                        -- Price as string (e.g. "6.49")
    unit_price REAL,                   -- Normalized $/100g or $/L (nullable, for future)
    size_raw TEXT,                     -- Extracted size (e.g. "4 L", "852 G")
    image_url TEXT,                    -- cutout_image_url from API
    valid_from TEXT NOT NULL,          -- Sale start date
    valid_to TEXT NOT NULL,            -- Sale end date
    scraped_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(flyer_id, product_name, store_name)  -- No duplicate items
);

CREATE INDEX IF NOT EXISTS idx_snapshots_store ON price_snapshots(store_name);
CREATE INDEX IF NOT EXISTS idx_snapshots_product ON price_snapshots(product_name);
CREATE INDEX IF NOT EXISTS idx_snapshots_valid ON price_snapshots(valid_from, valid_to);

CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    flyer_merchant_name TEXT NOT NULL,  -- Name as it appears in Flipp API
    address TEXT,
    active INTEGER DEFAULT 1
);
```

**Functions:**
- `init_db()` — Create tables if they don't exist, enable WAL mode
- `insert_snapshot(item: dict) -> bool` — Insert or ignore (returns True if new row created)
- `search_items(query: str, limit: int = 50) -> list[dict]` — LIKE search, ordered by price ASC
- `get_conn()` — Returns a connection with `row_factory = sqlite3.Row`

**Database location:** `data/prices.db` (version-controlled in git, auto-committed by the daily workflow)

### 5.3 Product Matcher (`matcher/engine.py`)

Canadian grocery flyers are a bilingual nightmare. Product names look like:
```
"LAIT 2% 4L | 2% MILK 4L"
"BURGERS DE POULET JERK PC | JERK CHICKEN BURGERS, 852 G"
"FROMAGE CHEDDAR PC | PC CHEDDAR CHEESE, 400 G"
```

**Functions:**

1. **`clean_name(raw: str) -> str`**
   - Split on `|` (bilingual separator)
   - Take the English half if available (the side after `|`), otherwise French
   - Uppercase everything
   - Strip punctuation: commas, periods, semicolons, colons, parentheses, brackets
   - Collapse multiple spaces
   - Return normalized string for comparison

2. **`extract_size(raw: str) -> str | None`**
   - Regex: `(\d+[\.,]?\d*\s*(?:G|KG|LB|L|ML|UN\.?|EA|CT|OZ|PAQUET|SAC))`
   - Returns size string or None
   - Examples: "4L", "852 G", "6 UN.", "1.5 L", "400 G"

3. **`extract_brand(name: str) -> str | None`**
   - Check against a known list of ~80 brands common in Quebec flyers
   - Includes store brands (PC, Sans Nom, Irrésistible, Compliments, Sélection Mérite)
   - Includes national brands (Kraft, Christie, Québon, Saputo, etc.)
   - Returns matched brand as .title() or None

4. **`match_score(name_a: str, name_b: str) -> float`**
   - Returns 0-100 similarity score
   - Uses `rapidfuzz` library (token_sort_ratio + partial_ratio, take max)
   - Falls back to word-overlap scoring if rapidfuzz not installed
   - **Thresholds:** >80 = same product, >60 = possibly same, <50 = different

5. **`group_similar(items: list[dict], threshold: float = 75.0) -> dict[str, list[dict]]`**
   - Clusters items into groups representing the same product across stores
   - Returns `{canonical_name: [items]}` — each group is the same product at different stores/prices
   - Example output: `{"2% MILK 4L": [{store:Maxi, price:6.49}, {store:Super C, price:5.99}]}`

**Dependencies:** `rapidfuzz>=3.0` for fuzzy matching.

### 5.4 Daily Orchestrator (`scrapers/run_all.py`)

**Entry point:** `python -m scrapers.run_all`

**Flow:**
1. Initialize database (`init_db()`)
2. Create `FlippClient` with `locale="en"`
3. Call `get_flyers("J3Y6J8")` → `filter_grocery()` → get list of active flyers
4. For each flyer, call `get_flyer_items(flyer_id)` and `insert_snapshot()` for each item
5. Print summary: total items, new items, breakdown by store
6. Print database stats (total rows, distinct stores)

**Error handling:** Skip failed flyers gracefully, continue with others. Log warnings to stderr.

**Output format (console):**
```
[2026-05-22T10:00:00+00:00] Starting daily scrape...
Found 9 grocery flyers:
  - Maxi (flyer #1234567)
  - Super C (flyer #1234568)
  ...
  ✓ Maxi: 342 items
  ✓ Super C: 287 items
  ...
Done. 2847 items (142 new) across 9 stores.
  Adonis: 215
  Costco: 178
  ...
Database now has 12847 items across 9 stores.
```

---

## 6. CI/CD Pipeline (GitHub Actions)

### 6.1 CI Workflow (`.github/workflows/ci.yml`)

**Triggers:** Push to `main`, pull requests to `main`

**Jobs:**
1. **Lint** — `ruff check .` (Python linting with modern rules)
2. **Test** (needs lint) — `pytest tests/ -v --cov=. --cov-report=term-missing`
3. **Smoke test** (needs test) — Verify Flipp API still responds, assert we get >=5 grocery flyers with items

### 6.2 Daily Scrape Workflow (`.github/workflows/scrape.yml`)

**Triggers:** Cron at `0 10 * * *` (6 AM Eastern = 10 AM UTC), also manual `workflow_dispatch`

**Job:**
1. Checkout repo
2. Setup Python 3.11
3. `pip install -e .`
4. `python -m scrapers.run_all`
5. Auto-commit: `git add data/` → if changes, commit with timestamp → `git push`

**Git config for bot:**
```
user.name "jarvis-bot"
user.email "jarvis@openclaw.local"
```

---

## 7. Project Structure

```
grocery-price-tracker/
├── .github/
│   └── workflows/
│       ├── ci.yml              # Lint → test → smoke
│       └── scrape.yml          # Daily cron scraper
├── scrapers/
│   ├── __init__.py
│   ├── flipp_client.py         # Flipp API client
│   └── run_all.py              # Daily orchestrator
├── matcher/
│   ├── __init__.py
│   └── engine.py               # Name normalization + fuzzy matching
├── db/
│   ├── __init__.py
│   └── models.py               # SQLite schema + CRUD
├── tests/
│   ├── __init__.py
│   ├── test_flipp_client.py    # Mock-based API client tests
│   └── test_matcher.py         # Unit tests for name cleaning + matching
├── data/
│   └── prices.db               # SQLite database (version controlled)
├── .gitignore
├── pyproject.toml              # Project config + dependencies
└── README.md                   # Documentation
```

---

## 8. Dependencies

```toml
[project]
name = "grocery-price-tracker"
version = "0.1.0"
description = "Daily grocery price comparison for Saint-Hubert, QC via Flipp flyer API"
requires-python = ">=3.10"
dependencies = [
    "requests>=2.31",      # HTTP client for Flipp API
    "sqlalchemy>=2.0",     # ORM (optional — raw sqlite3 is fine too)
    "rapidfuzz>=3.0",      # Fast fuzzy string matching (C-extended)
    "pydantic>=2.0",       # Data validation (optional, for future API)
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",         # Testing framework
    "pytest-cov>=5.0",     # Coverage reports
    "ruff>=0.5",           # Fast Python linter
]
```

---

## 9. Key Design Decisions

1. **Flipp API over per-store scraping** — 10 websites would require 10 different parsers, handling anti-bot measures, login walls, rate limits, and layout changes. Flipp gives us all stores in one call, with structured JSON, product images included, and zero auth. The tradeoff: Flipp only has flyer (sale) items, not everyday prices. This is actually what you want — you're hunting deals.

2. **SQLite over PostgreSQL** — No server to manage. A single file. Can be committed to git for version history. For a dataset of ~50K rows (10 stores × 500 items × 10 weeks), SQLite is more than sufficient.

3. **Git as data store** — Instead of running a database server, the daily scrape commits the SQLite file back to the repo. This gives you free version history, diffs on price changes, and no infrastructure costs. The tradeoff: concurrent writes are impossible, but that's fine for a daily cron job.

4. **Python (not JS/TS)** — Simpler for data processing. The ecosystem for fuzzy matching, data manipulation, and quick scripts is stronger. GitHub Actions has first-class Python support.

5. **No scraping framework needed** — No Playwright, no Selenium, no BeautifulSoup. The Flipp API returns clean JSON. `requests` is all you need.

---

## 10. Build Phases

### Phase 0 — Discovery ✅ (COMPLETED)
- Catalogued all grocery stores around Saint-Hubert
- Verified each is on Flipp
- Confirmed the Flipp API is accessible and returns useful data
- Identified the postal code, API structure, and item schema

### Phase 1 — Core Scraper ✅ (COMPLETED)
- Flipp API client with flyer filtering
- SQLite database schema
- `run_all.py` orchestrator
- Basic `search_items()` function

### Phase 2 — Smart Matching ✅ (COMPLETED)
- Bilingual name normalization
- Brand extraction from product names
- Fuzzy matching (rapidfuzz)
- Product grouping across stores

### Phase 3 — CI/CD ✅ (COMPLETED — needs GitHub push)
- CI workflow (lint + test + smoke)
- Daily scrape workflow (cron + auto-commit)
- GitHub repository setup

### Phase 4 — Dashboard 🚧 (NEXT)
Build a simple web interface:
- **Framework:** FastAPI (Python) or a static HTML/JS page reading from the SQLite
- **Features:**
  - Search bar: type "milk" → see all milk products across stores, sorted by price
  - Product detail: show image, price history over time, store comparison
  - Price alerts: notify when an item drops below a threshold
  - Mobile-friendly (Alex will use this on phone)
- **Hosting:** GitHub Pages (static) or a free-tier service (Render, Fly.io)

### Phase 5 — Canonical Basket 🚧
- Define ~50 common grocery items (milk, bread, eggs, butter, chicken, etc.)
- Manually map product name variations to canonical names
- Enable "my basket" tracking — what does this week's basket cost at each store?

### Phase 6 — Price Analytics 🚧
- Unit price normalization: convert everything to $/100g or $/L
- Price history charts (per product, per store)
- Best day to shop analysis
- Flyer cycle detection (which day of the week do prices drop?)

---

## 11. How to Build This (For Hermes AI)

### Step-by-step build order:

1. **Create the project structure** — `pyproject.toml`, directories, `.gitignore`
2. **Build the database layer** — `db/models.py` with schema + insert/search functions
3. **Build the Flipp client** — `scrapers/flipp_client.py` with all four methods
4. **Build the orchestrator** — `scrapers/run_all.py` that ties client + DB together
5. **Build the matcher** — `matcher/engine.py` with all five functions + brand list
6. **Write tests** — mock the API, test the matcher edge cases
7. **Create CI workflow** — `.github/workflows/ci.yml`
8. **Create scrape workflow** — `.github/workflows/scrape.yml`
9. **Write README** — document how to install, run, and search
10. **Run first scrape** — populate the database with real data
11. **Test search** — verify you can search and get meaningful results
12. **Push to GitHub** — set up remote and push everything

### Critical Gotchas:
- The `sid` parameter must be exactly 16 digits (not shorter, not longer)
- Product names are bilingual — always handle the `|` separator
- Some flyers have 0 items (expired or not yet published) — handle gracefully
- The `cutout_image_url` field is what you want for product photos (transparent background, high-res)
- `INSERT OR IGNORE` on the unique constraint prevents duplicates across runs
- The daily workflow needs write permissions to push commits (GitHub Actions default is fine)
- The `locale` parameter affects which language the product names come in — use `en` to favor English

---

## 12. Current Status

| Component | Status |
|-----------|--------|
| Flipp API client | ✅ Built & tested |
| Database schema | ✅ Built |
| Daily orchestrator | ✅ Built |
| Product matcher | ✅ Built |
| Unit tests | ✅ Written |
| CI workflow | ✅ Defined |
| Daily scrape workflow | ✅ Defined |
| GitHub repo | ❌ Not pushed yet |
| Dashboard | ❌ Not started |
| Canonical basket | ❌ Not started |
| Price analytics | ❌ Not started |

**GitHub token:** Available (expires Aug 20, 2026)

**Next action:** Push to GitHub → run first scrape → begin Phase 4 (Dashboard)
