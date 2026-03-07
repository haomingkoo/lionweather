# 🚨 URGENT: Backend Data Collection Not Running

## Problem Summary

**The backend is NOT collecting new weather data!**

### Current Status:

- ❌ Last data: March 13, 2026 (6 days ago)
- ❌ Only Malaysia collecting (Singapore/Indonesia = 0 records)
- ❌ Database not growing
- ❌ Background polling task not active

### Root Cause:

**Backend server on Railway is either:**

1. Not running at all
2. Crashed during startup
3. Background tasks failed to start

## Immediate Action Required

### 1. Check if Backend is Running

Visit: https://lionweather.kooexperience.com/api/health

**If this fails → Backend is DOWN**

### 2. Check Railway Logs

1. Go to Railway dashboard
2. Select `lionweather-backend` service
3. Click "Logs" tab
4. Look for startup messages:
   ```
   STARTING WEATHER APP - BACKGROUND SERVICES
   ✓ Data collector started (collects every 10 minutes)
   ```

**If you don't see this → Background tasks didn't start**

### 3. Redeploy Backend

```bash
cd lionweather
git add .
git commit -m "Fix: Add status endpoint and manual collection trigger"
git push origin main
```

Railway will auto-deploy in ~2-3 minutes.

### 4. Add Railway Volume (CRITICAL!)

**Without this, database resets on every deploy!**

1. Railway dashboard → `lionweather-backend` service
2. Click "Volumes" tab
3. Click "New Volume"
4. Mount path: `/app`
5. Click "Add"
6. Redeploy service

### 5. Test Manual Collection

After backend is running:

```bash
curl -X POST https://lionweather.kooexperience.com/api/admin/collect-now
```

Expected response:

```json
{
  "success": true,
  "collected": 300+,
  "stored": 300+,
  "by_country": {
    "singapore": 50+,
    "malaysia": 200+,
    "indonesia": 50+
  }
}
```

### 6. Verify Status

```bash
curl https://lionweather.kooexperience.com/api/status
```

Should show:

```json
{
  "status": "healthy",
  "database": {
    "exists": true,
    "stats": {
      "total_records": 2000+,
      "records_last_hour": 300+
    }
  }
}
```

## What I Fixed

### Added to `app/main.py`:

1. **`/status` endpoint** - Shows if backend is healthy and database stats
2. **`/admin/collect-now` endpoint** - Manually trigger data collection for testing
3. **Better logging** - More detailed startup and collection logs

### Files Modified:

- `lionweather/backend/app/main.py` - Added status and manual collection endpoints
- `lionweather/backend/app/services/data_collector.py` - Already has detailed logging
- `lionweather/BACKEND_POLLING_FIX.md` - Full diagnosis and fix guide
- `lionweather/URGENT_BACKEND_FIX_NEEDED.md` - This file

## Expected Behavior After Fix

### Every 10 Minutes:

```
[Collection #1] Starting data collection from all sources...
🇸🇬 Singapore: 50 records
🇲🇾 Malaysia: 284 records
🇮🇩 Indonesia: 30 records
[Collection #1] ✓ Stored 364/364 records
[Collection #1] Next collection in 10 minutes...
```

### Database Growth:

- **Per hour:** ~2,000 records (6 collections × 300-400 records)
- **Per day:** ~48,000 records
- **Per week:** ~336,000 records

## Why This Matters

**Without continuous data collection:**

- ❌ ML models can't train on recent data
- ❌ Forecasts become stale and inaccurate
- ❌ Can't beat NEA forecasts (our goal!)
- ❌ App shows old weather data

**With continuous data collection:**

- ✅ Fresh data every 10 minutes
- ✅ ML models train on latest patterns
- ✅ Accurate forecasts
- ✅ Can compare ML vs NEA performance

## Next Steps After Backend is Fixed

1. ✅ Verify data collecting from all 3 countries
2. ✅ Wait 24 hours for sufficient recent data
3. ✅ Run ML training: `python train_initial_models.py`
4. ✅ Monitor forecast accuracy
5. ✅ Research advanced ML techniques to beat NEA

## Need Help?

Check these files:

- `BACKEND_POLLING_FIX.md` - Detailed diagnosis and troubleshooting
- `RAILWAY_SETUP.md` - Railway deployment guide
- Railway logs - Real-time backend status

**Priority: HIGH** - Fix this ASAP to resume data collection!

## Data Quality: Duplicate Handling

### Automatic Duplicate Prevention

The database now automatically handles duplicates using `ON CONFLICT` clause:

- Records with same (timestamp, country, location) are **updated** instead of duplicated
- No manual cleanup needed for new collections
- Ensures data quality automatically

### Manual Duplicate Removal

If you suspect duplicates exist from previous collections:

**Check for duplicates (dry run):**

```bash
curl -X POST "https://lionweather.kooexperience.com/api/admin/remove-duplicates?dry_run=true"
```

**Remove duplicates:**

```bash
curl -X POST "https://lionweather.kooexperience.com/api/admin/remove-duplicates?dry_run=false"
```

**Or use the Python script:**

```bash
cd lionweather/backend
python remove_duplicates.py          # Dry run (shows what would be deleted)
python remove_duplicates.py --execute  # Actually remove duplicates
```

### What Gets Removed

When duplicates are found:

- ✅ Keeps the **most recent** record (by created_at timestamp)
- ❌ Removes older duplicate records
- 📊 Reports how many records were removed

This ensures you always have clean, high-quality data for ML training!
