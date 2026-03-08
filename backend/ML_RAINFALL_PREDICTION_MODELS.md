# ML Rainfall Prediction Models - Implementation Summary

## Overview

This document describes the Prophet baseline ML models for **RAINFALL PREDICTION** - Singapore's primary weather challenge. Temperature in Singapore is stable (26-32°C), but rainfall is highly variable and impacts daily life.

**Implementation Date**: 2026-03-08
**Task**: 5.1 - Create Prophet baseline ML model for RAINFALL PREDICTION

## Models Created

### 1. Rainfall Classifier (`train_rainfall_classifier.py`)

**Purpose**: Binary classification - Will it rain? (yes/no)

**Location**: `lionweather/backend/ml/train_rainfall_classifier.py`

**Target Variable**: Binary (1 = rain, 0 = no rain)

- Threshold: >0.5mm/hour = "raining"

**Features**:

- **Current conditions**: humidity (CRITICAL!), pressure, wind_speed, wind_direction, temperature
- **Historical rainfall**: rainfall_lag_1h, rainfall_lag_3h, rainfall_lag_6h, rainfall_lag_24h
- **Time patterns**: hour_sin, hour_cos, day_sin, day_cos
- **Monsoon indicators**: is_ne_monsoon (Nov-Jan), is_sw_monsoon (May-Sep)
- **Humidity/pressure trends**: humidity_change_1h, pressure_drop_3h
- **Wind direction**: wind_from_west (Sumatra squalls indicator)

**Forecast Horizons**: 1h, 3h, 6h, 12h, 24h ahead

**Validation**: TimeSeriesSplit (5-fold temporal cross-validation)

- NO random shuffling
- Strict temporal ordering
- NO data leakage

**Success Criteria**:

- Accuracy > 75%
- Precision > 0.70 (when we predict rain, we're right 70% of time)
- Recall > 0.70 (we catch 70% of rain events)
- F1-Score > 0.70

**Output**:

- Models: `models/rainfall_classifier/prophet_rainfall_classifier_{horizon}h.pkl`
- Metrics: `metrics/rainfall_classifier/prophet_rainfall_classifier_{horizon}h_metrics.json`

### 2. Rainfall Regressor (`train_rainfall_regressor.py`)

**Purpose**: Regression - How much rain? (mm/hour)

**Location**: `lionweather/backend/ml/train_rainfall_regressor.py`

**Target Variable**: Continuous (rainfall intensity in mm/hour)

**Features**: Same as classifier

- **Current conditions**: humidity, pressure, wind_speed, wind_direction, temperature
- **Historical rainfall**: rainfall_lag_1h, rainfall_lag_3h, rainfall_lag_6h, rainfall_lag_24h
- **Time patterns**: hour_sin, hour_cos, day_sin, day_cos
- **Monsoon indicators**: is_ne_monsoon, is_sw_monsoon
- **Humidity/pressure trends**: humidity_change_1h, pressure_drop_3h
- **Wind direction**: wind_from_west

**Forecast Horizons**: 1h, 3h, 6h, 12h, 24h ahead

**Validation**: TimeSeriesSplit (5-fold temporal cross-validation)

- NO random shuffling
- Strict temporal ordering
- NO data leakage

**Success Criteria**:

- MAE < 2mm/hour for 3-hour forecasts
- RMSE < 3mm/hour for 3-hour forecasts
- Beat NEA 2-hour nowcast by >10%

**Output**:

- Models: `models/rainfall_regressor/prophet_rainfall_regressor_{horizon}h.pkl`
- Metrics: `metrics/rainfall_regressor/prophet_rainfall_regressor_{horizon}h_metrics.json`

## Two-Stage Prediction Approach

The rainfall prediction system uses a two-stage approach:

1. **Stage 1 - Classification**: Will it rain? (yes/no)

   - Use rainfall classifier to predict probability of rain
   - If probability > 0.5, proceed to Stage 2

2. **Stage 2 - Regression**: How much rain? (mm/hour)
   - Use rainfall regressor to predict rainfall intensity
   - Only run if Stage 1 predicts rain

This approach is more efficient and accurate than predicting intensity directly for all cases.

## Key Features for Rainfall Prediction

### Why These Features?

Based on comprehensive time series analysis (HISTORICAL_DATA_ANALYSIS_2022_2025.md):

1. **Humidity** (CRITICAL):

   - Strong positive correlation with rainfall
   - High humidity → rain likely
   - Rapid humidity increase (humidity_change_1h) → rain imminent

2. **Pressure**:

   - Negative correlation with rainfall
   - Pressure drop (pressure_drop_3h) → rain likely
   - Barometric pressure is a leading indicator

3. **Historical Rainfall**:

   - rainfall_lag_1h: Strongest predictor (ACF = 0.353)
   - rainfall_lag_3h: Moderate predictor (ACF = 0.125)
   - rainfall_lag_24h: Daily pattern (ACF = 0.139)

4. **Monsoon Seasons**:

   - NE Monsoon (Nov-Jan): Wetter period
   - SW Monsoon (May-Sep): Wetter period
   - Inter-monsoon: Drier, but thunderstorms

5. **Wind Direction**:

   - Wind from west/southwest → Sumatra squalls (heavy rain)
   - Wind direction: 225-315° = from Sumatra

6. **Time Patterns**:
   - Cyclical encoding (sin/cos) for hour and day of year
   - Captures daily and seasonal patterns

## Data Leakage Prevention

### CRITICAL: Zero Tolerance for Data Leakage

Both training scripts implement strict data leakage prevention:

1. **Temporal Ordering**:

   - Data sorted chronologically
   - Train/val/test splits are temporal (not random)
   - TimeSeriesSplit ensures train < validation always

2. **Feature Engineering**:

   - Only use past data for features (lagged features)
   - NO future data in training set
   - NO smoothing across split boundaries

3. **Validation**:

   - TimeSeriesSplit (5-fold temporal cross-validation)
   - Validation set is always AFTER training set
   - Test set never seen during training

4. **Mock Data Detection**:
   - `validate_no_mock_data()` function checks for:
     - Mock source APIs (contains "mock", "fake", "test")
     - Suspicious repeated values (>100 identical consecutive)
     - Unrealistic patterns (constant non-zero rainfall >24h)
   - Training aborts if mock data detected

## Training Pipeline

### Prerequisites

1. Historical data seeded (Task 4 complete)

   - 2-3 years of hourly weather data
   - ~26,280 records (3 years × 365 days × 24 hours)
   - Source: Open-Meteo Historical API

2. Database schema:
   - Table: `weather_records`
   - Columns: timestamp, rainfall, humidity, pressure, wind_speed, wind_direction, temperature, source_api
   - Filter: `country = 'Singapore'`

### Running the Training Scripts

```bash
# Navigate to backend directory
cd lionweather/backend

# Train rainfall classifier (will it rain?)
python3 ml/train_rainfall_classifier.py

# Train rainfall regressor (how much rain?)
python3 ml/train_rainfall_regressor.py
```

### Training Process

For each horizon (1h, 3h, 6h, 12h, 24h):

1. **Load Data**:

   - Query database for Singapore weather records
   - Sort by timestamp (temporal ordering)
   - Validate no mock data

2. **Create Features**:

   - Extract time features (hour, day_of_year, month)
   - Cyclical encoding (sin/cos)
   - Monsoon indicators
   - Lagged rainfall features
   - Humidity/pressure trends
   - Wind direction indicators

3. **Prepare Prophet Data**:

   - Create target variable (shifted by horizon)
   - Rename columns for Prophet (ds, y)
   - Drop NaN values

4. **Cross-Validation**:

   - TimeSeriesSplit (5 folds)
   - Train on past, validate on future
   - Calculate metrics for each fold
   - Average metrics across folds

5. **Train Final Model**:

   - Use 80% for training, 20% for testing
   - Temporal split (train < test)
   - Evaluate on test set

6. **Save Model**:
   - Save trained Prophet model (.pkl)
   - Save metrics (.json)
   - Save training summary

### Expected Output

After training, you should see:

```
==============================================================
TRAINING SUMMARY - RAINFALL CLASSIFIER
==============================================================

Horizon | CV F1   | Test F1 | Test Acc | Test Prec | Test Rec | Success
--------------------------------------------------------------------------------
 1h     | 0.XXX   | 0.XXX   | 0.XXX    | 0.XXX     | 0.XXX    | ✅/❌
 3h     | 0.XXX   | 0.XXX   | 0.XXX    | 0.XXX     | 0.XXX    | ✅/❌
 6h     | 0.XXX   | 0.XXX   | 0.XXX    | 0.XXX     | 0.XXX    | ✅/❌
12h     | 0.XXX   | 0.XXX   | 0.XXX    | 0.XXX     | 0.XXX    | ✅/❌
24h     | 0.XXX   | 0.XXX   | 0.XXX    | 0.XXX     | 0.XXX    | ✅/❌

==============================================================
✅ RAINFALL CLASSIFIER TRAINING COMPLETE
==============================================================
```

## Model Architecture

### Prophet Model Configuration

```python
model = Prophet(
    daily_seasonality=True,      # 24-hour patterns
    weekly_seasonality=True,     # 7-day patterns
    yearly_seasonality=True,     # Seasonal patterns
    changepoint_prior_scale=0.05,  # Flexibility for trend changes
    seasonality_prior_scale=10.0,  # Strength of seasonality
)

# Add regressors (features)
model.add_regressor('hour_sin')
model.add_regressor('hour_cos')
model.add_regressor('day_sin')
model.add_regressor('day_cos')
model.add_regressor('humidity')
model.add_regressor('pressure')
model.add_regressor('wind_speed')
model.add_regressor('temperature')
model.add_regressor('is_ne_monsoon')
model.add_regressor('is_sw_monsoon')
model.add_regressor('rainfall_lag_1h')
model.add_regressor('rainfall_lag_3h')
model.add_regressor('rainfall_lag_6h')
model.add_regressor('rainfall_lag_24h')
model.add_regressor('humidity_change_1h')
model.add_regressor('pressure_drop_3h')
model.add_regressor('wind_from_west')
```

## Evaluation Metrics

### Classification Metrics (Rainfall Classifier)

- **Accuracy**: % of correct predictions (rain vs no rain)
- **Precision**: Of all "rain" predictions, how many were correct?
  - Formula: `TP / (TP + FP)`
  - Interpretation: "When we predict rain, we're right X% of the time"
- **Recall**: Of all actual rain events, how many did we catch?
  - Formula: `TP / (TP + FN)`
  - Interpretation: "We catch X% of all rain events"
- **F1-Score**: Harmonic mean of precision and recall
  - Formula: `2 × (Precision × Recall) / (Precision + Recall)`
  - Interpretation: "Balanced measure of prediction quality"
- **ROC-AUC**: Area under ROC curve (discrimination ability)
- **Confusion Matrix**: TP, FP, TN, FN

### Regression Metrics (Rainfall Regressor)

- **MAE (Mean Absolute Error)**: Average prediction error in mm/hour
  - Formula: `mean(|predicted - actual|)`
  - Interpretation: "On average, rainfall predictions are off by X mm/hour"
- **RMSE (Root Mean Square Error)**: Penalizes large errors more heavily
  - Formula: `sqrt(mean((predicted - actual)²))`
  - Interpretation: "Typical rainfall error is X mm/hour (larger errors weighted more)"
- **R² (Coefficient of Determination)**: Proportion of variance explained
  - Formula: `1 - (SS_residual / SS_total)`
  - Interpretation: "Model explains X% of rainfall variance"
- **MAPE (Mean Absolute Percentage Error)**: Relative error as percentage

## Next Steps

After training the models:

1. **Task 5.2**: Evaluate baseline model performance

   - Run comprehensive metrics and diagnostics
   - Compare against NEA 2-hour nowcast
   - Compare against persistence model
   - Analyze temporal performance (by time of day, season, intensity)

2. **Task 5.3**: Create historical data visualization page

   - Display training data overview
   - Show year-over-year patterns
   - Display time series decomposition
   - Show autocorrelation and frequency analysis

3. **Task 5.4**: Integrate ML predictions into UI

   - Display rainfall probability
   - Display rainfall intensity
   - Show confidence intervals
   - Add source indicator ("🤖 ML Model" vs "🌐 Open-Meteo")

4. **Task 5.5**: Create ML model performance dashboard

   - Display current model stats
   - Show accuracy metrics with explanations
   - Display model version history
   - Show forward-looking performance

5. **Task 5.6**: Implement continuous learning pipeline

   - Daily updates: Fetch actual weather data
   - Compare predictions vs actuals
   - Weekly retraining: Update models with new data
   - Validate: NO mock data in training batches

6. **Task 5.7**: Add ML model monitoring and validation

   - Model versioning system
   - Model comparison system
   - Performance monitoring
   - Data validation pipeline

7. **Task 5.8**: Store ML predictions for retrospective evaluation
   - Prediction storage
   - Actual outcome storage
   - Version-specific performance tracking
   - Retrospective analysis

## References

- **ML_FORECASTING_STRATEGY.md**: Research-based approach to ML forecasting
- **HISTORICAL_DATA_ANALYSIS_2022_2025.md**: Comprehensive time series analysis
- **Prophet Documentation**: https://facebook.github.io/prophet/
- **TimeSeriesSplit**: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html

## Success Criteria

### Rainfall Classifier

- ✅ Accuracy > 75%
- ✅ Precision > 0.70
- ✅ Recall > 0.70
- ✅ F1-Score > 0.70
- ✅ ROC-AUC > 0.80

### Rainfall Regressor

- ✅ MAE < 2mm/hour for 3-hour forecasts
- ✅ RMSE < 3mm/hour for 3-hour forecasts
- ✅ Beat NEA 2-hour nowcast by >10%
- ✅ Recall > 0.70 (catch at least 70% of rain events)

## Implementation Status

- ✅ Rainfall classifier script created (`ml/train_rainfall_classifier.py`)
- ✅ Rainfall regressor script created (`ml/train_rainfall_regressor.py`)
- ✅ Feature engineering implemented (humidity, pressure, wind, monsoon, lags)
- ✅ Data leakage prevention implemented (TimeSeriesSplit, temporal ordering)
- ✅ Mock data validation implemented (zero tolerance)
- ✅ Model architecture documented (Prophet with regressors)
- ✅ Evaluation metrics documented (classification + regression)
- ⏭️ Models need to be trained (requires dependencies installation)
- ⏭️ Performance evaluation (Task 5.2)
- ⏭️ UI integration (Task 5.4)

## Notes

- **PRIMARY TARGET**: RAINFALL (not temperature)
- **Why rainfall?**: Temperature in Singapore is stable (26-32°C), but rainfall is highly variable
- **Two-stage approach**: First predict if rain, then predict how much
- **CRITICAL**: Zero tolerance for mock/synthetic data in training
- **CRITICAL**: Strict temporal ordering to prevent data leakage
- **CRITICAL**: TimeSeriesSplit for cross-validation (no random shuffling)

---

**Last Updated**: 2026-03-08
**Status**: Implementation Complete - Ready for Training
**Task**: 5.1 - Create Prophet baseline ML model for RAINFALL PREDICTION
