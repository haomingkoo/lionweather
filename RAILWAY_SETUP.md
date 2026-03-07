# Railway Deployment Guide for LionWeather

## Overview

LionWeather requires **2 separate Railway services**:

1. **Backend** (Python/FastAPI) - API server
2. **Frontend** (React/Vite) - Web interface

## Step 1: Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose `haomingkoo/lioneweather`
5. Railway will detect it's a monorepo

## Step 2: Deploy Backend Service

### Create Backend Service

1. Click "Add Service" → "GitHub Repo"
2. Select your `lioneweather` repo
3. Name it: `lionweather-backend`

### Configure Backend

1. Go to service settings → **Root Directory**: `backend`
2. Go to **Variables** tab and add:

```
DATABASE_PATH=/app/weather.db
WEATHERAPI_KEY=your_actual_api_key_here
```

Optional alert variables (if you want notifications):

```
ALERT_EMAIL_ENABLED=false
ALERT_SLACK_ENABLED=false
ALERT_DISCORD_ENABLED=false
```

### Backend Build Settings

Railway will auto-detect Python and use `backend/railway.json`:

- Builder: NIXPACKS
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Get Backend URL

After deployment, copy the backend URL (looks like: `https://lionweather-backend-production.up.railway.app`)

## Step 3: Deploy Frontend Service

### Create Frontend Service

1. Click "Add Service" → "GitHub Repo"
2. Select your `lioneweather` repo again
3. Name it: `lionweather-frontend`

### Configure Frontend

1. Go to service settings → **Root Directory**: `frontend`
2. Go to **Variables** tab and add:

```
VITE_API_URL=https://your-backend-url-from-step-2.up.railway.app
```

### Frontend Build Settings

Create `frontend/railway.json`:

```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "npm run build && npm run preview -- --host 0.0.0.0 --port $PORT"
  }
}
```

## Step 4: Database Persistence (Important!)

Railway provides ephemeral storage by default. For persistent database:

### Option A: Railway Volume (Recommended)

1. Go to backend service → **Volumes** tab
2. Click "Add Volume"
3. Mount path: `/app`
4. This persists `weather.db` across deployments

### Option B: Railway PostgreSQL (Advanced)

1. Add PostgreSQL service to project
2. Update backend code to use PostgreSQL instead of SQLite
3. Set `DATABASE_URL` environment variable

## Step 5: Verify Deployment

### Check Backend

Visit: `https://your-backend-url.up.railway.app/docs`

- Should see FastAPI Swagger docs
- Test `/health` endpoint

### Check Frontend

Visit: `https://your-frontend-url.up.railway.app`

- Should load the LionWeather UI
- Try adding a location

## Environment Variables Summary

### Backend Required:

- `DATABASE_PATH=/app/weather.db`
- `WEATHERAPI_KEY=<your_key>`

### Frontend Required:

- `VITE_API_URL=<backend_url>`

### Optional (Alerts):

- `ALERT_EMAIL_ENABLED=false`
- `ALERT_SLACK_ENABLED=false`
- `ALERT_DISCORD_ENABLED=false`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` (if email enabled)
- `SLACK_WEBHOOK_URL` (if Slack enabled)
- `DISCORD_WEBHOOK_URL` (if Discord enabled)

## Troubleshooting

### Backend won't start

- Check logs: Railway dashboard → Backend service → Logs
- Verify `WEATHERAPI_KEY` is set
- Ensure root directory is `backend`

### Frontend can't connect to backend

- Verify `VITE_API_URL` points to backend URL (no trailing slash)
- Check CORS settings in `backend/app/main.py`
- Ensure backend is running

### Database resets on deploy

- Add a Railway Volume mounted at `/app`
- Or migrate to PostgreSQL for production

### Build fails

- Check `railway.json` exists in service root
- Verify dependencies in `pyproject.toml` / `package.json`
- Check Railway build logs

## Auto-Deploy from GitHub

Railway automatically deploys when you push to `main`:

```bash
git add .
git commit -m "Update feature"
git push origin main
```

Both services will rebuild and redeploy automatically.

## Custom Domains (Optional)

1. Go to service settings → **Domains**
2. Click "Add Domain"
3. Add your custom domain
4. Update DNS records as instructed

Example:

- Backend: `api.lionweather.com`
- Frontend: `lionweather.com`

## Cost Estimate

Railway free tier includes:

- $5 credit/month
- Enough for small apps

Typical usage:

- Backend: ~$3-5/month
- Frontend: ~$2-3/month
- Total: ~$5-8/month

## Next Steps

After deployment:

1. Test all features (locations, weather refresh, ML predictions)
2. Monitor logs for errors
3. Set up custom domain (optional)
4. Configure alerts (optional)
5. Add more weather stations

---

**Need help?** Check Railway docs: https://docs.railway.app
