# LionWeather

Singapore weather intelligence — NEA real-time data, ML-powered rainfall forecasting with SHAP analysis, and animated radar.

Live: [weather.kooexperience.com](https://weather.kooexperience.com)

---

## What it does

- **Real-time conditions** — pulls from Singapore's [data.gov.sg](https://api-open.data.gov.sg) every 10 minutes: temperature, rainfall, humidity, wind speed/direction, UV index, visibility, pressure
- **7-day forecast** — NEA 4-day outlook (Tue–Fri) + today's data from Open-Meteo, extended to 7 days; days labelled by actual SGT date (no mislabelling)
- **Hourly forecast** — next 24 hours from Open-Meteo with weather icons and precip probability; sunset/sunrise slots inserted chronologically
- **Weather detail cards** — Feels Like (Steadman heat index), Humidity (dew point), Wind (compass, hidden when no direction), Rainfall (NEA intensity legend), Visibility, Pressure, UV Index
- **Sunrise / Sunset card** — live arc tracking sun position; after sunset flips to "Sunrise Tomorrow" with a night arc and moon dot
- **Rainfall intensity legend** — Light / Moderate / Heavy / Intense colour dots on both the Rainfall card and the Map radar controls
- **Rain category labels** — each forecast day labelled No Rain / Light Rain / Heavy + Thundery, aligned to NEA's categories
- **NEA area name snapping** — pins resolve to the nearest official NEA neighbourhood (Ang Mo Kio, Tampines, etc.)
- **Radar** — animated rain area radar from weather.gov.sg with scrub slider and intensity legend; play button works on mobile
- **ML-Powered Forecast** — 6-hour ensemble prediction displayed in-card with generated time shown in SGT
- **ML Analysis Dashboard** — full data science view:
  - EDA: annual rainfall, rain category breakdown (with interpretation), temperature trend, STL decomposition (with interpretation)
  - ACF/PACF: variable-specific interpretations for rainfall, temperature, humidity, wind speed
  - FFT spectral analysis and spurious correlations
  - Training Loss Curves with per-curve health notes and interpretation
  - SHAP feature importance
  - Classification performance: confusion matrix, precision/recall/F2
  - NEA benchmark tables sorted by Rain F2 descending
- **Geolocation** — single browser prompt (no double-ask); location stored in browser only, never sent to server

---

## How to use the app

1. **Open** [weather.kooexperience.com](https://weather.kooexperience.com)
2. **Add your location** — click "📍 Use my location" in the sidebar; your browser will ask once for permission. Your location stays in your browser — never sent to our servers.
3. **Add more locations** — type a place name or drop a pin on Map View; names snap to official NEA neighbourhood names
4. **View forecast** — click any card to see NEA forecast with rain labels, hourly breakdown, radar, and detailed weather cards
5. **ML Dashboard** — shows time-series analysis, SHAP feature importance, training loss curves, and accuracy metrics vs NEA
6. **Notifications** — allow browser notifications to get rain start/clear alerts at tracked locations

---

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | FastAPI + PostgreSQL (Railway) / SQLite (local) |
| ML | LightGBM + SHAP + statsmodels |
| Sun times | SunCalc (pure JS, no API) |
| Rate limiting | slowapi |
| Deployment | Railway (separate frontend + backend services) |
| Data | Singapore data.gov.sg API (NEA) + Open-Meteo |

---

## Project structure

```
lionweather/
├── frontend/
│   └── src/
│       ├── components/             # UI components
│       │   ├── DetailedWeatherCard.jsx   # Forecast + detail cards + sun arc
│       │   ├── WeatherMap.jsx            # Leaflet map + NEA radar overlay
│       │   ├── MLAnalysisDashboard.jsx   # Full ML analysis view
│       │   └── MLForecastComparison.jsx  # In-card ML 6h forecast
│       ├── hooks/useLocations.jsx  # Location state, weather refresh, notifications
│       ├── api/                    # API client functions
│       ├── utils/sunTimes.js       # SunCalc sunrise/sunset/tomorrow helpers
│       └── pages/Dashboard.jsx
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, CORS, startup, scheduler, admin endpoints
│   │   ├── routers/                # API endpoints (forecasts, ml_forecast, environmental…)
│   │   ├── services/               # Data collection, radar, weather API
│   │   ├── db/                     # SQLite + migrations
│   │   └── ml/                     # ML scheduler, prediction engine
│   ├── ml/                         # Training scripts — run locally
│   │   ├── train_full_analysis.py  # Main: EDA + ACF/PACF + SHAP + 4-class + 3-class + NEA benchmark
│   │   ├── feature_engineer.py
│   │   ├── nea_classification.py   # Rain category definitions
│   │   └── data_validation.py
│   ├── models/                     # ML output artifacts (committed to git)
│   │   └── full_analysis.json      # Generated by train_full_analysis.py
│   ├── requirements.txt
│   └── pyproject.toml
└── railway.toml
```

---

## Running locally

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # set ADMIN_SECRET and optionally WEATHER_API_KEY

uvicorn app.main:app --reload --port 8000
```

API docs at `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App at `http://localhost:5173` — proxies `/api` to `localhost:8000`

---

## ML training workflow (local → Railway)

Training runs **locally** — the historical NEA dataset is too large for Railway:

```bash
cd backend
source venv/bin/activate

# Full analysis: EDA, SHAP, 4-class + 3-class classifiers, NEA regional benchmark
python -m ml.train_full_analysis
```

This writes `backend/models/full_analysis.json`. Commit and push — Railway serves it via `/api/ml/full-analysis`.

**Rain categories:**

App uses 3-class (better accuracy, more actionable):
| Class | Label | Rainfall |
|-------|-------|---------|
| 0 | No Rain | < 0.1 mm/hr |
| 1 | Light Rain | 0.1–7.6 mm/hr |
| 2 | Heavy + Thundery | ≥ 7.6 mm/hr |

Benchmarking vs NEA uses 4-class:
| Class | Label | Rainfall |
|-------|-------|---------|
| 0 | No Rain | < 0.1 mm/hr |
| 1 | Light Rain | < 7.6 mm/hr |
| 2 | Heavy Rain | < 30 mm/hr |
| 3 | Thundery Showers | ≥ 30 mm/hr |

**Training data:** NEA historical CSVs 2016–2024 in `backend/nea_historical_data/` (gitignored, ~46 GB).
Temporal split: train 2016–2022 / val 2023 / test 2024. No data leakage — all lag features use `.shift()`, strict year-based split.

**Top SHAP features:** `dry_spell_hours` (#1, 4.41), `humidity` (#2), `wind_accel_3h` (#3, 2.47 — captures squall line approach).

**Model accuracy (test 2024):** 1h = 69.9%, 3h = 62.2%, 6h = 59.2%, 12h = 57.5%

---

## Historical benchmark (`benchmark_historical.py`)

Evaluates ML model performance against NEA official forecasts over historical data (2016–2024).

```bash
cd backend
source venv/bin/activate
python benchmark_historical.py
# writes models/historical_benchmark.json
```

**Methodology** — for each 2-hour NEA forecast window `[T, T+2h]`:

| System | How it predicts |
|--------|-----------------|
| **NEA** | Binary: majority vote across 47 NEA areas (≥ 50% areas forecast rain → 1) |
| **ML Nh** | LightGBM classifier run at `T − N hours`, using only weather_records before that time |
| **Hybrid** | 60% ML probability + 40% NEA binary, ≥ 0.5 → 1 |
| **Persistence** | Was it actually raining in the previous 2h window? (naive baseline) |
| **Ground truth** | Mean total mm across all 64 rainfall stations in `[T, T+2h]` ≥ 1.0 mm → actual rain |

Outputs per-year and aggregated accuracy, F1, precision, recall, and specificity for each system.
Results are written to `backend/models/historical_benchmark.json` (committed to git, ~10KB).
Served via Railway at `GET /api/ml/historical-benchmark`.

---

## Admin endpoints

Protected by `X-Admin-Secret` header (set `ADMIN_SECRET` env var on Railway):

```
POST /admin/retrain           — trigger ML retraining on the Railway instance
GET  /admin/retrain-status    — poll retraining progress and log tail
POST /admin/collect-now       — force immediate weather data collection
POST /admin/collect-forecasts — force forecast data collection
GET  /admin/export            — export all weather records as JSON
POST /admin/remove-duplicates — deduplicate weather records table
```

---

## Monitoring live data collection

Railway polls NEA every 10 minutes:

```
GET /api/status                — data counts, latest timestamps, scheduler state
GET /api/data-health/status    — health score, row counts, gap detection
GET /api/data-health/gaps      — specific time gaps (>15 min = warning)
GET /api/data-health/quality   — completeness, validity, duplicates
GET /api/data-health/timeline  — records per hour for last 7 days
```

Full interactive API reference at `/docs`.

---

## Environment variables

```env
ADMIN_SECRET=          # required — protects all /admin/* endpoints
DATABASE_PATH=         # optional — defaults to weather.db (set to /app/data/weather.db if using Railway Volume)
```

Set in Railway → Variables for the backend service.

### Railway Volume (recommended for SQLite persistence)

Without a Volume, the SQLite database resets on every redeploy:

1. Railway → backend service → Settings → Volumes → Add Volume → mount at `/app/data`
2. Set `DATABASE_PATH=/app/data/weather.db`

---

## Deployment

Both services deploy from the same repo on push to `main` via `railway.toml`:

- Frontend: `npm run build` → static files served by Railway
- Backend: `uvicorn app.main:app` via `Procfile`

CORS is configured in `backend/app/main.py` to allow `https://weather.kooexperience.com`.

---

## Built by

[Haoming Koo](https://kooexperience.com) with [Claude](https://claude.ai) (Anthropic).
