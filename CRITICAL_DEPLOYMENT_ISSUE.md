# CRITICAL: Backend Not Deployed

## Issue Summary

The backend API is **NOT accessible** in production. All requests to `https://lionweather.kooexperience.com/api/*` are returning the frontend HTML instead of JSON responses from the FastAPI backend.

## Evidence

```bash
$ curl https://lionweather.kooexperience.com/api/health
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>LionWeather</title>
    ...
```

**Expected**: `{"status": "healthy"}`
**Actual**: Frontend HTML

## Root Cause

Railway is only deploying the **frontend** service at `https://lionweather.kooexperience.com`. The **backend** service is either:

1. Not deployed at all
2. Deployed but not accessible
3. Deployed at a different URL that we don't know

## Architecture Problem

The current setup assumes:

- Frontend: Static files served by `npx serve`
- Backend: FastAPI server on a different service
- Frontend calls backend via `/api/*` paths

**Problem**: Static file servers like `npx serve` don't have routing/proxy capabilities. They serve files from disk. When you request `/api/health`, it tries to find a file at `dist/api/health` and falls back to `index.html`.

## Solution Options

### Option 1: Deploy Backend as Separate Railway Service (RECOMMENDED)

**Steps**:

1. **Create Backend Service on Railway**:

   - Go to Railway dashboard
   - Create new service from `lionweather/backend` directory
   - Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Deploy and get the backend URL (e.g., `https://lionweather-backend-production.up.railway.app`)

2. **Configure Frontend to Use Backend URL**:

   - In Railway frontend service, add environment variable:
     ```
     VITE_API_BASE_URL=https://lionweather-backend-production.up.railway.app
     ```
   - Rebuild frontend with this variable

3. **Update Frontend API Calls**:

   - Modify `frontend/src/api/backend.js` to use `VITE_API_BASE_URL`:
     ```javascript
     const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";
     ```

4. **Configure CORS on Backend**:
   - Ensure backend allows requests from frontend domain:
     ```python
     app.add_middleware(
         CORSMiddleware,
         allow_origins=["https://lionweather.kooexperience.com"],
         allow_credentials=True,
         allow_methods=["*"],
         allow_headers=["*"],
     )
     ```

**Pros**:

- Clean separation of concerns
- Backend can scale independently
- Easy to debug and monitor

**Cons**:

- Requires two Railway services (may cost more)
- Need to configure CORS
- Frontend needs to know backend URL

### Option 2: Use Railway Proxy/Routing

**Steps**:

1. **Configure Railway to route `/api/*` to backend service**
2. **Keep frontend at root path**

**Note**: This requires Railway Pro plan or custom domain configuration.

### Option 3: Serve Frontend from Backend (SIMPLE)

**Steps**:

1. **Build frontend**: `cd frontend && npm run build`
2. **Copy `dist/` to backend**: `cp -r frontend/dist backend/static`
3. **Configure FastAPI to serve static files**:

   ```python
   from fastapi.staticfiles import StaticFiles

   # API routes
   app.include_router(weather_router, prefix="/api")

   # Serve frontend static files
   app.mount("/", StaticFiles(directory="static", html=True), name="static")
   ```

4. **Deploy only backend service**

**Pros**:

- Single service (simpler, cheaper)
- No CORS issues
- No need for separate frontend deployment

**Cons**:

- Backend serves static files (not ideal for scaling)
- Need to rebuild backend when frontend changes
- Mixed concerns (API + static files)

## Immediate Action Required

**Current Status**: ❌ Backend is NOT functional in production

**Impact**:

- Frontend cannot fetch weather data
- No data collection happening
- Database not being populated
- ML models cannot be trained
- Application is essentially broken

**Priority**: 🔴 CRITICAL - Must be fixed before any other tasks

## Recommended Fix (Option 1)

1. **Deploy Backend Service**:

   ```bash
   # In Railway dashboard:
   # 1. New Service → Deploy from GitHub
   # 2. Select lionweather repository
   # 3. Set root directory: lionweather/backend
   # 4. Set start command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   # 5. Add environment variables:
   #    - DATABASE_URL (PostgreSQL connection string)
   #    - Any other required env vars
   # 6. Deploy
   ```

2. **Get Backend URL**:

   - After deployment, Railway will provide a URL like:
     `https://lionweather-backend-production.up.railway.app`

3. **Configure Frontend**:

   ```bash
   # In Railway frontend service settings:
   # Add environment variable:
   VITE_API_BASE_URL=https://lionweather-backend-production.up.railway.app

   # Redeploy frontend
   ```

4. **Update Frontend Code** (if needed):

   ```javascript
   // frontend/src/api/backend.js
   const API_BASE = import.meta.env.VITE_API_BASE_URL
     ? import.meta.env.VITE_API_BASE_URL + "/api"
     : "/api";
   ```

5. **Verify**:

   ```bash
   # Test backend directly
   curl https://lionweather-backend-production.up.railway.app/api/health
   # Should return: {"status":"healthy"}

   # Test from frontend
   # Open browser DevTools → Network tab
   # Should see requests to backend URL
   ```

## Next Steps After Fix

Once backend is deployed and accessible:

1. ✅ Verify `/api/health` returns JSON
2. ✅ Verify `/api/status` shows database stats
3. ✅ Check Railway logs for background task startup
4. ✅ Wait 10 minutes and verify data collection
5. ✅ Test frontend integration
6. ✅ Monitor for 24 hours

## Files to Update

### Frontend Changes

**File**: `lionweather/frontend/src/api/backend.js`

```javascript
// Current (development only):
const API_BASE = "/api";

// Updated (works in production):
const API_BASE = import.meta.env.VITE_API_BASE_URL
  ? import.meta.env.VITE_API_BASE_URL + "/api"
  : "/api";
```

**File**: `lionweather/frontend/src/api/radar.js`

```javascript
// Already has this pattern - good!
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
```

**File**: `lionweather/frontend/src/api/regional.js`

```javascript
// Already has this pattern - good!
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
```

### Backend Changes

**File**: `lionweather/backend/app/main.py`

Verify CORS configuration includes frontend domain:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Development
        "https://lionweather.kooexperience.com",  # Production frontend
        "https://lionweather-frontend-production.up.railway.app",  # Railway frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Testing Checklist

After deployment:

- [ ] Backend `/api/health` returns JSON (not HTML)
- [ ] Backend `/api/status` returns database stats
- [ ] Backend logs show "STARTING WEATHER APP - BACKGROUND SERVICES"
- [ ] Backend logs show data collection starting
- [ ] Frontend Network tab shows requests to backend URL
- [ ] Frontend displays weather data
- [ ] No CORS errors in browser console
- [ ] Database is being populated (check `/api/status` after 10 min)

## Contact

If you need help with Railway deployment:

- Railway Docs: https://docs.railway.app/
- Railway Discord: https://discord.gg/railway
