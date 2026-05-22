# 🛒 Grocery Price Tracker — Saint-Hubert, QC

Daily price comparison across 9 grocery stores in Saint-Hubert, powered by the Flipp flyer API.

## How It Works

```
Flipp API → 1 Python client → SQLite DB → Dashboard (TBD)
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
│   ├── ci.yml           # Lint → test → smoke on push/PR
│   └── scrape.yml       # Daily cron (6 AM Eastern)
├── scrapers/
│   ├── flipp_client.py  # Flipp API client
│   └── run_all.py       # Orchestrator
├── matcher/
│   └── engine.py        # Product name normalization + fuzzy matching
├── db/
│   └── models.py        # SQLite models
├── data/
│   └── prices.db        # Price history (versioned)
├── tests/
│   ├── test_flipp_client.py
│   └── test_matcher.py
└── pyproject.toml
```

## Quick Start

```bash
# Install
pip install -e .

# Run scraper (takes ~30s)
python -m scrapers.run_all

# Search
python -c "
from db.models import search_items
for item in search_items('lait'):
    print(item)
"
```

## CI/CD

- **On push/PR**: Lint (ruff), unit tests, smoke test (verifies API still works)
- **Daily at 6 AM ET**: Full scrape, auto-commits data back to repo
- **Failure alert**: OpenClaw cron monitors for 3 consecutive failures

## Data

Each item captured:
- Product name (bilingual)
- Brand
- Price (sale/flyer price)
- Product image URL (high-res)
- Valid from/to dates
- Store name

## Next

- [ ] Dashboard (web interface for search + comparison)
- [ ] Product canonical basket (50 common items manually mapped)
- [ ] Price history charts
- [ ] Unit price normalization ($/100g, $/L)
