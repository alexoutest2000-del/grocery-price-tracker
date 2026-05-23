# 🛒 Grocery Price Tracker — Saint-Hubert, QC

Daily price comparison across 9 grocery stores in Saint-Hubert, powered by the Flipp flyer API.

**Live dashboard:** [alexoutest2000-del.github.io/grocery-price-tracker/dashboard/](https://alexoutest2000-del.github.io/grocery-price-tracker/dashboard/)

## How It Works

```
Flipp API → 1 Python client → SQLite DB → JSON export → Static Dashboard
```

One API endpoint. No Playwright. No anti-bot fighting. No per-store scrapers.

## Stores Covered

| Store | Source | Status |
|-------|--------|--------|
| Maxi | Flipp flyer | ✅ Live |
| Super C | Flipp flyer | ✅ Live |
| Metro | Flipp flyer | ✅ Live |
| IGA | Flipp flyer | ✅ Live |
| Provigo | Flipp flyer | ✅ Live |
| Walmart | Flipp flyer | ✅ Live |
| Adonis | Flipp flyer | ✅ Live |
| Avril Supermarché Santé | Flipp flyer | ✅ Live |
| Costco | Flipp flyer | ✅ Live |

## Architecture

```
grocery-price-tracker/
├── .github/workflows/
│   ├── ci.yml              # Lint → test → smoke on push/PR
│   └── scrape.yml          # Daily cron (6 AM Eastern)
├── scrapers/
│   ├── flipp_client.py     # Flipp API client
│   └── run_all.py          # Orchestrator + JSON export
├── matcher/
│   └── engine.py           # Product name normalization + fuzzy matching
├── db/
│   └── models.py           # SQLite models + export_json()
├── dashboard/
│   └── index.html          # Static searchable product grid
├── data/
│   ├── prices.db           # SQLite database (version-controlled)
│   └── prices.json         # JSON export for dashboard
├── tests/
│   ├── test_flipp_client.py
│   └── test_matcher.py
├── PLAN.md                 # Full technical plan
└── pyproject.toml
```

## Dependencies

| Dependency | Version | Purpose | Install |
|------------|---------|---------|---------|
| Python | 3.10+ | Runtime | `sudo apt install python3` |
| uv | latest | Package manager | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| requests | 2.31+ | HTTP client (Flipp API) | `uv sync` |
| sqlalchemy | 2.0+ | SQLite ORM | `uv sync` |
| rapidfuzz | 3.0+ | Fuzzy product matching | `uv sync` |
| pydantic | 2.0+ | Data validation | `uv sync` |
| pytest | 8.0+ | Testing (dev) | `uv sync --group dev` |
| ruff | 0.5+ | Linting (dev) | `uv sync --group dev` |

All managed via `uv` — a single `uv sync` installs everything.

## Quick Start

```bash
# Install dependencies
uv sync

# Run scraper (takes ~30s)
uv run python -m scrapers.run_all

# Search from CLI
uv run python -c "
from db.models import search_items
for item in search_items('lait'):
    print(item)
"
```

## CI/CD

- **On push/PR:** Lint (ruff), unit tests, smoke test (verifies API still works)
- **Daily at 6 AM ET:** Full scrape → JSON export → auto-commit `data/` back to repo
- **Dashboard:** GitHub Pages serves `dashboard/index.html` → fetches `data/prices.json` client-side

## Dashboard

Search any grocery item — results show product images, store names, and prices, cheapest first. Fully mobile-responsive.

URL: `https://alexoutest2000-del.github.io/grocery-price-tracker/dashboard/`

## Data

Each item captured:

- Product name (bilingual: French | English)
- Brand (extracted from name)
- Price (flyer/sale price)
- Product image URL (high-res cutout from Flipp)
- Valid from/to dates (sale period)
- Store name

## Status

- [x] Core scraper (Flipp API client + SQLite)
- [x] Product matcher (bilingual normalization + fuzzy matching)
- [x] CI/CD (GitHub Actions — lint, test, daily scrape)
- [x] Static dashboard (searchable product grid on GitHub Pages)
- [x] JSON export (auto-generated each scrape)
- [ ] Canonical basket (50 common items mapped)
- [ ] Price history charts
- [ ] Unit price normalization ($/100g, $/L)
