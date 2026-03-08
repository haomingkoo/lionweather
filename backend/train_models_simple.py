"""
Simple ML Model Training Script

Trains models using existing weather_records and forecast_data from the database.
Compares ML predictions with NEA official forecasts.
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import pickle
import os

print("=" * 80)
print("LIONWEATHER ML MODEL TRAINING")
print("=" * 80)

# Connect to database
db_path = os.getenv("DATABASE_PATH", "weather.db")
conn = sqlite3.connect(db_path)

# Load weather records
print("\n1. Loading weather data from database...")
weather_df = pd.read_sql_query("""
    SELECT 
        timestamp,
        country,
        location,
        temperature,
        humidity,
        wind_speed,
        rainfall
    FROM weather_records
    WHERE temperature IS NOT NULL
    ORDER BY timestamp
""", conn)

print(f"   Loaded {len(weather_df):,} weather records")
print(f"   Date range: {weather_df['timestamp'].min()} to {weather_df['timestamp'].max()}")
print(f"   Countries: {weather_df['country'].unique()}")

# Load forecast data
print("\n2. Loading NEA forecast data...")
forecast_df = pd.read_sql_query("""
    SELECT 
        timestamp,
        forecast_date,
        location,
        temperature_high,
        temperature_low,
        condition,
        country
    FROM forecast_data
    WHERE temperature_high IS NOT NULL
    ORDER BY timestamp
""", conn)

print(f"   Loaded {len(forecast_df):,} forecast records")

conn.close()

# Prepare training data
print("\n3. Preparing training data...")
weather_df['timestamp'] = pd.to_datetime(weather_df['timestamp'])
weather_df['hour'] = weather_df['timestamp'].dt.hour
weather_df['day_of_week'] = weather_df['timestamp'].dt.dayofweek
weather_df['month'] = weather_df['timestamp'].dt.month

# Create features
features = ['hour', 'day_of_week', 'month', 'humidity', 'wind_speed']
target = 'temperature'

# Remove rows with missing values
train_data = weather_df[features + [target]].dropna()

print(f"   Training samples: {len(train_data):,}")
print(f"   Features: {features}")

# Split data
X = train_data[features]
y = train_data[target]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print(f"   Train set: {len(X_train):,} samples")
print(f"   Test set: {len(X_test):,} samples")

# Train models
print("\n4. Training ML models...")

# Model 1: Random Forest
print("   Training Random Forest...")
rf_model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
rf_model.fit(X_train, y_train)
rf_pred = rf_model.predict(X_test)
rf_mae = mean_absolute_error(y_test, rf_pred)
rf_rmse = np.sqrt(mean_squared_error(y_test, rf_pred))

print(f"   ✓ Random Forest - MAE: {rf_mae:.2f}°C, RMSE: {rf_rmse:.2f}°C")

# Model 2: Gradient Boosting
print("   Training Gradient Boosting...")
gb_model = GradientBoostingRegressor(n_estimators=100, random_state=42)
gb_model.fit(X_train, y_train)
gb_pred = gb_model.predict(X_test)
gb_mae = mean_absolute_error(y_test, gb_pred)
gb_rmse = np.sqrt(mean_squared_error(y_test, gb_pred))

print(f"   ✓ Gradient Boosting - MAE: {gb_mae:.2f}°C, RMSE: {gb_rmse:.2f}°C")

# Save models
print("\n5. Saving trained models...")
os.makedirs("ml/models", exist_ok=True)

with open("ml/models/random_forest_temp.pkl", "wb") as f:
    pickle.dump(rf_model, f)
print("   ✓ Saved: ml/models/random_forest_temp.pkl")

with open("ml/models/gradient_boosting_temp.pkl", "wb") as f:
    pickle.dump(gb_model, f)
print("   ✓ Saved: ml/models/gradient_boosting_temp.pkl")

# Compare with NEA forecasts
print("\n6. Comparing with NEA forecasts...")
if len(forecast_df) > 0:
    forecast_df['forecast_date'] = pd.to_datetime(forecast_df['forecast_date'])
    forecast_df['timestamp'] = pd.to_datetime(forecast_df['timestamp'])
    
    # Calculate NEA forecast accuracy
    forecast_df['nea_temp_avg'] = (forecast_df['temperature_high'] + forecast_df['temperature_low']) / 2
    
    print(f"   NEA forecasts available: {len(forecast_df):,}")
    print(f"   Average forecast temp: {forecast_df['nea_temp_avg'].mean():.1f}°C")
    print(f"   Forecast range: {forecast_df['temperature_low'].min():.1f}°C - {forecast_df['temperature_high'].max():.1f}°C")
else:
    print("   No NEA forecast data available for comparison")

# Summary
print("\n" + "=" * 80)
print("TRAINING COMPLETE")
print("=" * 80)
print(f"\nModel Performance Summary:")
print(f"  Random Forest:      MAE = {rf_mae:.2f}°C, RMSE = {rf_rmse:.2f}°C")
print(f"  Gradient Boosting:  MAE = {gb_mae:.2f}°C, RMSE = {gb_rmse:.2f}°C")
print(f"\nBest Model: {'Random Forest' if rf_mae < gb_mae else 'Gradient Boosting'}")
print(f"\nModels saved to: ml/models/")
print(f"Database records: {len(weather_df):,} weather + {len(forecast_df):,} forecasts")
print("\nNext steps:")
print("  1. Models are ready for predictions")
print("  2. Use /api/ml/predict endpoint to get ML forecasts")
print("  3. Compare ML vs NEA forecasts in production")
print("=" * 80)
