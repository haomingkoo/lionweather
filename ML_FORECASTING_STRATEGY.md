# ML Weather Forecasting Strategy - Research-Based Approach

## Executive Summary

Based on current research (2024-2025), this document outlines a rigorous, production-ready approach to building ML weather forecasting models with **ZERO data leakage** and proper temporal validation.

## Critical Requirements

### ✅ NO Data Leakage

- **Temporal ordering MUST be preserved** - never train on future data
- **No random shuffling** - use TimeSeriesSplit or blocked cross-validation
- **No feature leakage** - features must only use data available at prediction time
- **No smoothing across train/test boundary** - no rolling windows that span splits

### ✅ Proper Time Series Validation

- **TimeSeriesSplit** - expanding window validation (sklearn)
- **Blocked cross-validation** - prevent memorization from overlapping data
- **Walk-forward validation** - simulate real-world deployment
- **Temporal train/val/test splits** - chronological, not random

### ✅ Real Data Only

- **NO mock/synthetic data** in training
- **NO data augmentation** that creates fake patterns
- **Validate all training batches** for real API sources

## Research Findings

### Model Comparison (2024-2025 Studies)

Based on [recent comparative studies](https://www.preprints.org/manuscript/202601.1377):

**ARIMA**:

- Best for: Simple linear patterns
- MAPE: 3.2-13.6%
- Pros: Fast, interpretable, good for short-term
- Cons: Struggles with non-linear patterns

**LSTM (Deep Learning)**:

- Best for: Complex non-linear dependencies
- Error reduction: 84-87% vs ARIMA on complex data
- Pros: Captures long-term dependencies, handles multivariate inputs
- Cons: Requires more data, computationally expensive, harder to interpret

**Prophet (Facebook)**:

- Best for: Strong seasonality, business time series
- MAPE: 2.2-24.2%
- Pros: Handles missing data, outliers, holidays
- Cons: May overfit on small datasets

### Recommended Approach for Singapore Weather

**Start with Prophet** for these reasons:

1. Strong daily/seasonal patterns in Singapore weather
2. Handles missing data gracefully (API failures)
3. Fast training and inference
4. Interpretable components (trend, seasonality, holidays)
5. Built-in uncertainty intervals
6. Good performance on temperature forecasting (MAPE 2.2-24.2%)

**Then add LSTM** if needed:

1. After establishing Prophet baseline
2. If non-linear patterns emerge
3. For longer-range forecasts (>24 hours)
4. When sufficient training data available (>6 months)

## Implementation Plan

### Phase 1: Prophet Baseline (Weeks 1-2)

**Goal**: Establish reliable 1-24 hour temperature forecasts

**Features**:

- Current temperature
- Hour of day (cyclical encoding)
- Day of year (seasonality)
- Humidity
- Wind speed
- Rainfall

**Validation Strategy**:

```python
from sklearn.model_selection import TimeSeriesSplit

# 5-fold temporal cross-validation
tscv = TimeSeriesSplit(n_splits=5)

for train_idx, val_idx in tscv.split(data):
    # Train on past data only
    train_data = data.iloc[train_idx]
    val_data = data.iloc[val_idx]

    # Fit Prophet model
    model.fit(train_data)

    # Predict on future data
    predictions = model.predict(val_data)

    # Evaluate
    mae = mean_absolute_error(val_data['y'], predictions['yhat'])
```

**Horizons**:

- 1 hour ahead (primary)
- 3 hours ahead
- 6 hours ahead
- 12 hours ahead
- 24 hours ahead

**Success Criteria**:

- MAE < 1.5°C for 1-hour forecasts
- MAE < 2.0°C for 3-hour forecasts
- MAE < 2.5°C for 6-hour forecasts
- MAE < 3.0°C for 12-hour forecasts
- MAE < 3.5°C for 24-hour forecasts

### Phase 2: LSTM Enhancement (Weeks 3-4)

**Goal**: Improve accuracy for complex patterns and longer horizons

**Architecture**:

```python
# Sequence-to-sequence LSTM
model = Sequential([
    LSTM(64, return_sequences=True, input_shape=(lookback, n_features)),
    Dropout(0.2),
    LSTM(32, return_sequences=False),
    Dropout(0.2),
    Dense(24)  # Predict next 24 hours
])
```

**Features**:

- Past 24 hours of temperature (sequence)
- Past 24 hours of humidity
- Past 24 hours of wind speed
- Past 24 hours of rainfall
- Hour of day (cyclical)
- Day of year (cyclical)

**Validation Strategy**:

```python
# Walk-forward validation
for i in range(n_splits):
    # Expanding window
    train_end = train_start + train_size + i * step_size
    test_start = train_end
    test_end = test_start + test_size

    # Ensure no overlap
    assert test_start > train_end

    # Train and evaluate
    model.fit(X_train[:train_end], y_train[:train_end])
    predictions = model.predict(X_test[test_start:test_end])
```

**Success Criteria**:

- Outperform Prophet by >10% on MAE
- Maintain temporal integrity (no leakage)
- Inference time < 100ms per prediction

### Phase 3: Ensemble (Week 5)

**Goal**: Combine Prophet + LSTM for robust predictions

**Strategy**:

- Use Prophet for short-term (1-6 hours)
- Use LSTM for medium-term (6-24 hours)
- Weighted average based on validation performance
- Display both predictions + confidence intervals in UI

## Data Leakage Prevention Checklist

### ✅ Before Training

- [ ] Data sorted chronologically
- [ ] Train/val/test splits are temporal (not random)
- [ ] No future data in training set
- [ ] Features only use past data
- [ ] No smoothing across split boundaries

### ✅ During Training

- [ ] TimeSeriesSplit or blocked CV used
- [ ] Validation set is always AFTER training set
- [ ] No data augmentation that creates fake patterns
- [ ] No hyperparameter tuning on test set

### ✅ After Training

- [ ] Test set never seen during training
- [ ] Predictions only use data available at prediction time
- [ ] Rolling windows don't span train/test boundary
- [ ] Model performance evaluated on truly unseen future data

## Validation Metrics

### Primary Metrics

- **MAE (Mean Absolute Error)**: Average prediction error in °C
- **RMSE (Root Mean Square Error)**: Penalizes large errors
- **MAPE (Mean Absolute Percentage Error)**: Relative error

### Secondary Metrics

- **Directional Accuracy**: % of correct up/down predictions
- **Peak Detection**: Accuracy on temperature extremes
- **Confidence Calibration**: Are uncertainty intervals reliable?

### Baseline Comparisons

- **Persistence Model**: Tomorrow = Today (naive baseline)
- **Open-Meteo API**: Compare against official forecasts
- **NEA Forecasts**: Compare against Singapore official forecasts

## Continuous Learning Pipeline

### Daily Updates

1. Fetch yesterday's actual weather data
2. Compare ML predictions vs actual outcomes
3. Calculate prediction errors
4. Append to training dataset
5. Validate: NO mock data in new batch
6. Store for next retraining cycle

### Weekly Retraining

1. Retrain Prophet model on updated dataset
2. Validate on most recent week (walk-forward)
3. Compare performance vs previous model
4. Deploy if MAE improves by >5%
5. Log model version and performance

### Monthly Evaluation

1. Comprehensive performance review
2. Analyze error patterns (time of day, weather conditions)
3. Identify model drift
4. Consider LSTM retraining (more expensive)
5. Update ensemble weights if needed

## Implementation Files

### Core Files

- `train_prophet_model.py` - Prophet training script
- `train_lstm_model.py` - LSTM training script
- `evaluate_models.py` - Validation and metrics
- `predict.py` - Inference endpoint
- `continuous_learning.py` - Daily update pipeline

### Validation Files

- `validate_no_leakage.py` - Data leakage detection
- `temporal_cv.py` - TimeSeriesSplit implementation
- `walk_forward_validation.py` - Walk-forward testing

### Monitoring Files

- `monitor_performance.py` - Track MAE over time
- `detect_drift.py` - Model drift detection
- `validate_training_data.py` - Reject mock data

## References

### Research Papers

- [Comparative Study of ARIMA, LSTM and Prophet Models (2025)](https://www.preprints.org/manuscript/202601.1377) - Model comparison
- [Heavy Rain High Stakes: Can AI Forecasts Be Trusted? (2025)](https://completeaitraining.com/news/heavy-rain-high-stakes-can-ai-forecasts-be-trusted/) - Leakage control best practices

### Best Practices

- [Advanced Time Series CV Techniques](https://www.numberanalytics.com/blog/advanced-time-series-cv-techniques) - Blocked validation
- [Avoiding Data Leakage with TimeSeriesSplit](https://codecut.ai/cross-validation-with-time-series/) - Temporal validation
- [How Data Leakage Affects LSTM Evaluation](https://arxiv.org/html/2512.06932v1) - LSTM-specific leakage issues

### Tools

- **Prophet**: [facebook/prophet](https://facebook.github.io/prophet/)
- **TimeSeriesSplit**: [sklearn.model_selection.TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
- **LSTM**: [tensorflow.keras.layers.LSTM](https://www.tensorflow.org/api_docs/python/tf/keras/layers/LSTM)

## Success Criteria

### Technical

- ✅ MAE < 2.0°C for 3-hour forecasts
- ✅ No data leakage detected in validation
- ✅ Inference time < 100ms
- ✅ Model retraining < 10 minutes
- ✅ 100% real data (zero mock data)

### Business

- ✅ More accurate than persistence model
- ✅ Competitive with Open-Meteo forecasts
- ✅ User trust: Display confidence intervals
- ✅ Transparent: Show "ML Prediction" vs "Official Forecast"
- ✅ Continuous improvement: MAE decreases over time

## Next Steps

1. ✅ Historical data seeded (Task 4 complete)
2. ⏭️ Implement Prophet baseline (Task 5.1)
3. ⏭️ Evaluate Prophet performance (Task 5.2)
4. ⏭️ Integrate predictions into UI (Task 5.3)
5. ⏭️ Implement continuous learning (Task 5.4)
6. ⏭️ Add monitoring and validation (Task 5.5)
7. ⏭️ Store predictions for evaluation (Task 5.6)

---

**Last Updated**: 2026-03-08
**Status**: Research Complete - Ready for Implementation
**Approved By**: User (confirmed research-based approach)
