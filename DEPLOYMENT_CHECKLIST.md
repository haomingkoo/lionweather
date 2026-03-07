# 🚀 LionWeather Deployment Checklist

## ✅ What Was Just Fixed and Pushed

### Backend Improvements:

1. ✅ **Status Endpoint** (`/status`) - Shows backend health, database stats, recent activity
2. ✅ **Manual Collection** (`/admin/collect-now`) - Trigger data collection for testing
3. ✅ **Duplicate Removal** (`/admin/remove-duplicates`) - Clean duplicate records
4. ✅ **Automatic Duplicate Prevention** - ON CONFLICT handling in database
5. ✅ **Comprehensive Logging** - Detailed logs for Singapore/Indonesia/Malaysia collection
6. ✅ **Data Quality Script** - `remove_duplicates.py` for local cleanup

### ML Infrastructure:

7. ✅ **NEA Forecast Collection** - Added `fetch_nea_forecast()` method
8. ✅ **ML Dashboard Methodology Tab** - Shows data leakage prevention techniques
9. ✅ **ML Dashboard Performance Metrics Tab** - Shows MAE, RMSE, MAPE, NEA comparison
10. ✅ **Data Leakage Fix** - Applied `.shift(1)` to all rolling features
11. ✅ **Comprehensive Tests** - Property-based tests for all bugs

### Frontend Improvements:

12. ✅ **Lat/Lng Readability** - Changed to `text-sm` with better contrast
13. ✅ **Add Current Location Button** - Re-add deleted geolocation
14. ✅ **Card Sizing** - Consistent, compact card dimensions
15. ✅ **Hourly Forecast Slider** - Horizontal scrolling forecast

## 🔴 URGENT: What You Need to Do NOW

### Step 1: Check if Backend is Running

Visit: https://lionweather.kooexperience.com/api/health

**If this fails:**

1. Go to Railway dashboard
2. Check `lionweather-backend` service logs
3. Look for errors or crashes
4. Redeploy if needed

### Step 2: Add Railway Volume (CRITICAL!)

**Without this, database resets on every deploy!**

1. Railway dashboard → `lionweather-backend` service
2. Click "Volumes" tab
3. Click "New Volume"
4. Mount path: `/app`
5. Click "Add"
6. Redeploy service

### Step 3: Test Manual Collection

```bash
curl -X POST https://lionweather.kooexperience.com/api/admin/collect-now
```

Expected: 300+ records from all 3 countries

### Step 4: Check Status

```bash
curl https://lionweather.kooexperience.com/api/status
```

Should show:

- Database exists: true
- Total records: 2000+
- Records last hour: 300+

### Step 5: Remove Any Duplicates

```bash
# Check for duplicates
curl -X POST "https://lionweather.kooexperience.com/api/admin/remove-duplicates?dry_run=true"

# Remove if found
curl -X POST "https://lionweather.kooexperience.com/api/admin/remove-duplicates?dry_run=false"
```

### Step 6: Monitor Data Collection

Wait 10 minutes, then check status again. Records should be growing.

## 📊 Expected Behavior After Fix

### Every 10 Minutes:

- 🇸🇬 Singapore: ~50 records
- 🇲🇾 Malaysia: ~284 records
- 🇮🇩 Indonesia: ~30 records
- **Total: ~364 records per collection**

### Database Growth:

- Per hour: ~2,000 records
- Per day: ~48,000 records
- Per week: ~336,000 records

## 🤖 ML Training Next Steps

### After 24 Hours of Data Collection:

1. **Check Data Status:**

   ```bash
   cd lionweather/backend
   python check_data_status.py
   ```

2. **Train Initial Models:**

   ```bash
   python train_initial_models.py
   ```

3. **Monitor Training:**

   - Check Railway logs for training progress
   - Look for MAE, RMSE, MAPE metrics
   - Verify models are saved

4. **Test Predictions:**
   - Visit ML Dashboard
   - Check Methodology tab
   - Check Performance Metrics tab
   - Compare ML vs NEA forecasts

## 🎯 Goal: Beat NEA Forecasts

### Current Status:

- ✅ Data collection infrastructure ready
- ✅ ML pipeline with data leakage prevention
- ✅ NEA forecast collection for comparison
- ✅ Performance metrics dashboard
- ⏳ Waiting for continuous data collection
- ⏳ Need to train models on fresh data
- ⏳ Need to research advanced ML techniques

### Next Phase (After Backend is Fixed):

1. Ensure 24+ hours of continuous data collection
2. Train initial models (ARIMA, SARIMA, Prophet)
3. Evaluate performance vs NEA
4. Research advanced techniques:
   - Transformer models (Temporal Fusion Transformer)
   - N-BEATS, N-HiTS
   - Ensemble methods
   - Feature engineering from other domains
5. Implement best techniques to beat NEA

## 📝 Documentation

- `URGENT_BACKEND_FIX_NEEDED.md` - Quick fix guide
- `BACKEND_POLLING_FIX.md` - Detailed diagnosis
- `RAILWAY_SETUP.md` - Deployment guide
- `ML_TRAINING_PLAN.md` - ML training strategy

## ⚠️ Common Issues

### Backend keeps crashing:

- Check Railway logs for Python errors
- Verify dependencies in `pyproject.toml`
- Check memory usage (Railway free tier: 512MB)

### Singapore/Indonesia still 0 records:

- Check Railway logs for API errors
- Verify rate limiting isn't blocking requests
- Check if APIs are accessible from Railway

### Database keeps resetting:

- **MUST add Railway Volume at `/app`**
- Without volume, database resets on every deploy

### Background task not starting:

- Check Railway logs for startup errors
- Verify `@app.on_event("startup")` is called
- Look for exception stack traces

## 🎉 Success Criteria

You'll know everything is working when:

1. ✅ `/health` endpoint returns healthy
2. ✅ `/status` shows database growing
3. ✅ All 3 countries collecting data
4. ✅ No duplicates in database
5. ✅ Records increasing every 10 minutes
6. ✅ ML models can train on data
7. ✅ Forecasts beating NEA accuracy

## 🆘 Need Help?

If issues persist after following this checklist:

1. Check Railway status: https://status.railway.app
2. Check API status:
   - Singapore: https://data.gov.sg
   - Malaysia: https://data.gov.my
   - Indonesia: https://bmkg.go.id
3. Review Railway logs for detailed errors
4. Check GitHub issues for similar problems

---

**Priority: HIGH** - Complete Steps 1-6 ASAP to resume data collection!
