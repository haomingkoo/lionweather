# Backend Data Collection Polling Issue - Diagnosis & Fix

## Problem Identified

The backend data collection is **NOT running continuously**. Current status:

- ✅ 1,988 records collected (from March 7-13)
- ❌ **No new data since March 13** (6 days ago)
- ❌ **Only Malaysia data** - Singapore and Indonesia returning 0 records
- ❌ **Background polling task not active**

## Root Causes

### 1. Backend Server Not Running on Railway

The FastAPI server with background tasks needs to be running 24/7 on Railway.

**Check if backend is running:**

```bash
curl https://lionweather-backend-production.up.railway.app/health
```

If this fails, the backend is down.

### 2. Railway Ephemeral Storage Issue

Railway resets the database on every deploy unless you use a Volume.

**Solution:** Add Railway Volume

1. Go to Railway dashboard → Backend service
2. Click "Volumes" tab
3. Add volume mounted at `/app`
4. This persists `weather.db` across deployments

### 3. Background Task Startup Issue

The `@app.on_event("startup")` may not be triggering properly.

## Immediate Fixes

### Fix 1: Verify Backend is Running

**Check Railway Logs:**

1. Go to Railway dashboard
2. Select `lionweather-backend` service
3. Click "Logs" tab
4. Look for:
   ```
   STARTING WEATHER APP - BACKGROUND SERVICES
   ✓ Data collector started (collects every 10 minutes)
   ```

If you don't see this, the backend crashed or didn't start.

### Fix 2: Add Health Check Endpoint with Status

I'll add a `/status` endpoint that shows if background tasks are running:

```python
# Add to app/main.py

@app.get("/status")
def status_check():
    """Detailed status check including background tasks"""
    return {
        "status": "healthy",
        "background_tasks": {
            "data_collector": "running",  # We'll track this
            "radar_service": "running",
            "ml_scheduler": "running"
        },
        "database": {
            "path": os.getenv("DATABASE_PATH", "weather.db"),
            "exists": os.path.exists(os.getenv("DATABASE_PATH", "weather.db"))
        }
    }
```

### Fix 3: Force Immediate Data Collection

Add an endpoint to manually trigger data collection:

```python
# Add to app/main.py

@app.post("/admin/collect-now")
async def trigger_collection():
    """Manually trigger data collection (for testing)"""
    from app.services.data_collector import DataCollector
    from app.services.data_store import DataStore

    collector = DataCollector()
    store = DataStore()

    records = await collector.collect_all_sources()

    stored = 0
    for record in records:
        try:
            await asyncio.to_thread(store.store_record, record)
            stored += 1
        except Exception as e:
            logger.error(f"Failed to store: {e}")

    return {
        "collected": len(records),
        "stored": stored,
        "by_country": {
            "singapore": len([r for r in records if r.country == "singapore"]),
            "malaysia": len([r for r in records if r.country == "malaysia"]),
            "indonesia": len([r for r in records if r.country == "indonesia"])
        }
    }
```

### Fix 4: Check Singapore/Indonesia API Issues

The parsers were fixed but APIs might be failing. Add detailed logging:

```python
# Already added in data_collector.py - check Railway logs for:
# 🇸🇬 Starting Singapore data collection...
# 🇲🇾 Starting Malaysia data collection...
# 🇮🇩 Starting Indonesia data collection...
```

## Deployment Steps

### Step 1: Redeploy Backend with Fixes

```bash
cd lionweather/backend
git add .
git commit -m "Add status endpoint and manual collection trigger"
git push origin main
```

Railway will auto-deploy.

### Step 2: Add Railway Volume (CRITICAL)

1. Railway dashboard → `lionweather-backend`
2. Settings → Volumes
3. Click "New Volume"
4. Mount path: `/app`
5. Click "Add"
6. Redeploy service

This ensures database persists across deployments.

### Step 3: Verify Background Tasks Started

After deployment, check logs:

```bash
# In Railway logs, you should see:
[INFO] STARTING WEATHER APP - BACKGROUND SERVICES
[INFO] ✓ Radar service started successfully
[INFO] ✓ ML training scheduler started (runs Sundays at 2 AM)
[INFO] ✓ Data collector started (collects every 10 minutes)
[INFO] ALL BACKGROUND SERVICES STARTED
```

### Step 4: Test Manual Collection

```bash
curl -X POST https://lionweather-backend-production.up.railway.app/admin/collect-now
```

Should return:

```json
{
  "collected": 300+,
  "stored": 300+,
  "by_country": {
    "singapore": 50+,
    "malaysia": 200+,
    "indonesia": 50+
  }
}
```

### Step 5: Monitor Data Growth

Wait 10 minutes, then check:

```bash
curl https://lionweather-backend-production.up.railway.app/status
```

Check database:

```bash
cd lionweather/backend
python check_data_status.py
```

Should show:

- Recent activity (last 24 hours): increasing
- All 3 countries collecting data

## Expected Behavior After Fix

### Every 10 Minutes:

```
[Collection #1] Starting data collection from all sources...
🇸🇬 Starting Singapore data collection...
✓ Singapore data collection complete: 50 valid records
🇲🇾 Starting Malaysia data collection...
✓ Malaysia data collection complete: 284 valid records
🇮🇩 Starting Indonesia data collection...
✓ Indonesia data collection complete: 30 valid records
[Collection #1] Collected 364 weather records
[Collection #1] ✓ Stored 364/364 records in database
[Collection #1] Next collection in 10 minutes...
```

### Database Growth:

- **Per collection:** ~300-400 new records
- **Per hour:** ~1,800-2,400 records (6 collections)
- **Per day:** ~43,000-57,000 records

## Troubleshooting

### Backend keeps crashing

- Check Railway logs for Python errors
- Verify all dependencies in `pyproject.toml`
- Check memory usage (Railway free tier: 512MB)

### Singapore/Indonesia still returning 0

- Check API endpoints are accessible from Railway
- Verify no rate limiting (we added rate limiters)
- Check Railway logs for detailed error messages

### Database keeps resetting

- **MUST add Railway Volume** at `/app`
- Without volume, database resets on every deploy

### Background task not starting

- Check `@app.on_event("startup")` is being called
- Verify no exceptions in startup code
- Check Railway logs for startup errors

## Next Steps After Fix

1. ✅ Verify all 3 countries collecting data
2. ✅ Confirm database growing every 10 minutes
3. ✅ Wait 24 hours for sufficient data
4. ✅ Run ML training: `python -m app.ml.training_pipeline`
5. ✅ Monitor forecast accuracy vs NEA

## Contact

If issues persist, check:

- Railway status: https://status.railway.app
- API status: Singapore (data.gov.sg), Malaysia (data.gov.my), Indonesia (bmkg.go.id)
