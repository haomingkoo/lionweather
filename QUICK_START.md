# Quick Start - Testing Your Fixes

## Step 1: Test the Backend API (2 minutes)

```bash
cd backend
python test_ml_api.py
```

**What this does:**

- Checks if backend is running
- Tests all ML endpoints
- Tests radar and rainfall endpoints
- Shows which endpoints work and which need data

**Expected output:**

```
✅ Backend is running
❌ FAIL - 24h Predictions (404 - No data)
❌ FAIL - 7d Predictions (404 - No data)
❌ FAIL - Current Weather (404 - No data)
✅ PASS - Accuracy Metrics
✅ PASS - Model Comparison
✅ PASS - Radar Frames (or FAIL if NEA API down)
✅ PASS - Rainfall Data (or FAIL if rate limited)
```

## Step 2: Seed Test Data (1 minute)

When the script asks:

```
⚠️  No weather data found. Would you like to seed test data?
Seed test data? (y/n):
```

Type `y` and press Enter.

**What this does:**

- Creates 30 days of hourly weather data
- Generates realistic Singapore weather patterns
- Enables ML forecasting features immediately

**Expected output:**

```
✅ Created 720 test weather records
```

## Step 3: Verify Frontend (1 minute)

1. Open browser: http://localhost:5173
2. Open DevTools Console (F12)
3. Navigate to ML Dashboard (if available in UI)

**What to check:**

- ✅ No console errors (except maybe external NEA API issues)
- ✅ Charts render correctly
- ✅ ML Dashboard shows predictions OR "Not Ready" message
- ✅ No "width(-1) and height(-1)" warnings

## Step 4: Test ML API Directly (Optional)

```bash
# Test 24h predictions
curl http://localhost:8000/api/ml/predictions/24h?country=Singapore

# Test current weather
curl http://localhost:8000/api/ml/predictions/current?country=Singapore

# Test accuracy metrics
curl http://localhost:8000/api/ml/metrics/accuracy?parameter=temperature
```

**Expected:**

- Should return JSON data (not 500 errors)
- 404 is OK if no data seeded yet
- 200 with data after seeding

## Troubleshooting

### Backend not running?

```bash
# If using flox:
flox services start

# Or manually:
cd backend
uvicorn app.main:app --reload
```

### Frontend not running?

```bash
cd frontend
npm run dev
```

### Still seeing errors?

1. Check backend logs for details
2. Check browser console for specific error messages
3. Verify database file exists: `backend/weather.db`
4. Try restarting both services

## What's Fixed

✅ Backend API methods (DataStore signatures)
✅ ML router (removed incorrect await)
✅ Chart sizing (explicit dimensions)
✅ Error boundaries (prevent crashes)
✅ Error logging (detailed debugging)

## What Needs External Setup

⏳ ML Data (use test script to seed)
⏳ NEA Radar API (external service issues)
⏳ Alert notifications (.env configuration)

## Success Criteria

After running the test script and seeding data:

1. **Backend**: All ML endpoints return 200 (not 500)
2. **Frontend**: No console errors except external API issues
3. **Charts**: Render correctly without warnings
4. **ML Dashboard**: Shows predictions or clean "Not Ready" message

That's it! Run the test script and you're done. 🎉
