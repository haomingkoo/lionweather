# ML Model Performance Report - Rainfall Prediction

**Generated**: 2025-03-08 (Framework Created)

**Task**: 5.2 - Evaluate baseline model performance with comprehensive metrics

**Status**: ⏳ Awaiting Model Training

---

## Executive Summary

This report will evaluate Prophet baseline models for **RAINFALL PREDICTION** - Singapore's primary weather challenge.

**Models to be Evaluated**:

- **Rainfall Classifier**: Binary classification (will it rain?)
- **Rainfall Regressor**: Regression (how much rain in mm/hour?)

**Forecast Horizons**: 1h, 3h, 6h, 12h, 24h ahead

**Note**: Models need to be trained first. Run:

```bash
cd lionweather/backend
python3 ml/train_rainfall_classifier.py
python3 ml/train_rainfall_regressor.py
python3 ml/evaluate_rainfall_models.py
```

---

## 1. Classification Metrics (Will It Rain?)

### Performance by Forecast Horizon

Classification metrics evaluate the model's ability to predict whether it will rain (binary: yes/no).

**Metrics Evaluated**:

| Metric        | Formula                                           | Interpretation                                       |
| ------------- | ------------------------------------------------- | ---------------------------------------------------- |
| **Accuracy**  | `(TP + TN) / Total`                               | % of correct predictions (rain vs no rain)           |
| **Precision** | `TP / (TP + FP)`                                  | When we predict rain, we're right X% of the time     |
| **Recall**    | `TP / (TP + FN)`                                  | We catch X% of all rain events                       |
| **F1-Score**  | `2 × (Precision × Recall) / (Precision + Recall)` | Balanced measure of prediction quality               |
| **ROC-AUC**   | Area under ROC curve                              | Discrimination ability (0.5 = random, 1.0 = perfect) |

**Confusion Matrix Components**:

- **True Positive (TP)**: Correctly predicted rain
- **False Positive (FP)**: False alarm (predicted rain, but didn't rain)
- **False Negative (FN)**: Missed rain event (predicted no rain, but it rained)
- **True Negative (TN)**: Correctly predicted no rain

### Success Criteria

✅ **Target Performance**:

- Accuracy > 75%
- Precision > 0.70 (minimize false alarms)
- Recall > 0.70 (catch at least 70% of rain events)
- F1-Score > 0.70 (balanced performance)
- ROC-AUC > 0.80 (strong discrimination)

---

## 2. Regression Metrics (How Much Rain?)

### Performance by Forecast Horizon

Regression metrics evaluate the model's ability to predict rainfall intensity (mm/hour).

**Metrics Evaluated**:

| Metric   | Formula                                           | Interpretation                              |
| -------- | ------------------------------------------------- | ------------------------------------------- |
| **MAE**  | `mean(\|predicted - actual\|)`                    | Average prediction error in mm/hour         |
| **RMSE** | `sqrt(mean((predicted - actual)²))`               | Typical error (penalizes large errors more) |
| **R²**   | `1 - (SS_residual / SS_total)`                    | Proportion of variance explained (0-1)      |
| **MAPE** | `mean(\|predicted - actual\| / \|actual\|) × 100` | Relative error as percentage                |

**Interpretation Examples**:

- **MAE = 1.5 mm/h**: On average, predictions are off by 1.5 mm/hour
- **RMSE = 2.0 mm/h**: Typical error is 2.0 mm/hour (larger errors weighted more)
- **R² = 0.85**: Model explains 85% of rainfall variance
- **MAPE = 25%**: Predictions are off by 25% on average

### Success Criteria

✅ **Target Performance**:

- MAE < 2mm/hour for 3-hour forecasts
- RMSE < 3mm/hour for 3-hour forecasts
- Beat NEA 2-hour nowcast by >10%
- R² > 0.70 (explain at least 70% of variance)

---

## 3. Temporal Performance Analysis

### Performance by Time of Day

Rainfall prediction accuracy varies by hour. Some hours are harder to predict:

- **Morning (6-9 AM)**: Typically drier, easier to predict
- **Afternoon (2-5 PM)**: Convective thunderstorms, harder to predict
- **Evening (6-9 PM)**: Transition period, moderate difficulty
- **Night (10 PM-5 AM)**: Generally stable, easier to predict

### Performance by Season

Singapore has distinct monsoon seasons affecting rainfall patterns:

**Seasons**:

- **NE Monsoon (Nov-Jan)**: Wetter period, more consistent rain
- **SW Monsoon (May-Sep)**: Wetter period, afternoon thunderstorms
- **Inter-monsoon (Feb-Apr, Oct)**: Drier, but sudden thunderstorms

**Expected Performance**:

- Monsoon seasons: Higher accuracy (more predictable patterns)
- Inter-monsoon: Lower accuracy (sudden convective storms)

### Performance by Weather Condition

Accuracy varies by weather type:

- **Clear/Sunny**: High accuracy (easy to predict no rain)
- **Cloudy**: Moderate accuracy (rain possible but not certain)
- **Light Rain**: Good accuracy (persistent patterns)
- **Heavy Rain/Thunderstorms**: Lower accuracy (sudden onset, high variability)

### Performance by Forecast Horizon

Accuracy degrades with longer forecast horizons (expected):

- **1h**: Highest accuracy (near-term persistence)
- **3h**: Good accuracy (short-term patterns)
- **6h**: Moderate accuracy (medium-term trends)
- **12h**: Lower accuracy (longer-term uncertainty)
- **24h**: Lowest accuracy (daily forecast limit)

---

## 4. Baseline Comparisons

### Baseline Models

**Persistence Model** (Naive Baseline):

- Assumption: Tomorrow's rain = Today's rain
- Formula: `rainfall(t+h) = rainfall(t)`
- Expected: Poor performance for rainfall (highly variable)

**Climatology Model** (Historical Average):

- Assumption: Use historical average for that day/hour
- Formula: `rainfall(t+h) = mean(historical_rainfall[day, hour])`
- Expected: Better than persistence, but misses short-term patterns

**Open-Meteo Forecasts** (International Weather Service):

- Professional weather service forecasts
- Benchmark for comparison

**NEA 2-Hour Nowcast** (Official Singapore Forecast):

- Singapore's official short-term rainfall forecast
- Target: Beat NEA by >10%

### Skill Score

**Formula**: `Skill = (MAE_baseline - MAE_model) / MAE_baseline × 100`

**Interpretation**:

- Positive skill score: Model is better than baseline
- Negative skill score: Model is worse than baseline
- Skill > 20%: Significant improvement
- Skill > 10%: Meaningful improvement

---

## 5. Residual Diagnostics

### Residual Analysis

Residuals = Actual - Predicted

**Diagnostic Tests**:

1. **Mean Residual (Bias)**:

   - Target: Close to 0 (no systematic over/under-prediction)
   - Interpretation: Mean residual = 0.1 mm/h → Model slightly over-predicts

2. **Normality Test (Shapiro-Wilk)**:

   - Target: p-value > 0.05 (residuals are normally distributed)
   - Interpretation: Normal residuals → Model assumptions are valid

3. **Autocorrelation (Lag-1)**:

   - Target: Close to 0 (no patterns in errors)
   - Interpretation: High autocorrelation → Model misses temporal patterns

4. **Heteroscedasticity Test**:
   - Target: Low correlation between |residuals| and predictions
   - Interpretation: Heteroscedasticity → Error variance increases with prediction magnitude

### Diagnostic Plots

**Residual Plot** (Residuals vs Predicted):

- Ideal: Random scatter around zero
- Patterns indicate: Model bias or missing features

**Q-Q Plot** (Quantile-Quantile):

- Ideal: Points follow diagonal line
- Deviations indicate: Non-normal residuals

**Histogram of Residuals**:

- Ideal: Bell-shaped curve centered at zero
- Skewness indicates: Systematic bias

**Predicted vs Actual**:

- Ideal: Points follow diagonal line (perfect prediction)
- Scatter indicates: Prediction error

---

## 6. Cross-Validation Results

### TimeSeriesSplit (5-Fold)

**CRITICAL**: TimeSeriesSplit ensures NO data leakage:

- Always train on past data
- Always validate on future data
- NO random shuffling
- Expanding window approach

**Fold Structure**:

```
Fold 1: Train [0:20%]    → Validate [20%:40%]
Fold 2: Train [0:40%]    → Validate [40%:60%]
Fold 3: Train [0:60%]    → Validate [60%:80%]
Fold 4: Train [0:80%]    → Validate [80%:90%]
Fold 5: Train [0:90%]    → Validate [90%:100%]
```

**Metrics Reported**:

- Mean ± Std Dev across folds
- Low std dev → Stable model performance
- High std dev → Model performance varies by time period

---

## 7. Feature Importance Analysis

### Permutation Importance

**Method**: Permute each feature and measure increase in prediction error.

**Expected Top Features for Rainfall Prediction**:

1. **Humidity** (CRITICAL):

   - High humidity → Rain likely
   - Rapid humidity increase → Rain imminent

2. **Pressure Drop**:

   - Barometric pressure drop → Rain likely
   - Leading indicator for weather changes

3. **Historical Rainfall** (Lags):

   - `rainfall_lag_1h`: Strongest predictor (persistence)
   - `rainfall_lag_3h`: Moderate predictor
   - `rainfall_lag_24h`: Daily pattern

4. **Wind Direction**:

   - Wind from west/southwest → Sumatra squalls (heavy rain)
   - Wind direction: 225-315° = from Sumatra

5. **Monsoon Season**:

   - NE Monsoon (Nov-Jan): Wetter period
   - SW Monsoon (May-Sep): Wetter period

6. **Time Patterns**:
   - Hour of day (cyclical): Afternoon thunderstorms
   - Day of year (cyclical): Seasonal patterns

**Validation**: Important features should make meteorological sense.

---

## 8. Success Criteria Evaluation

### Classification (Rainfall Probability)

**Target Criteria**:

- ✅ Accuracy > 75%
- ✅ Precision > 0.70 (minimize false alarms)
- ✅ Recall > 0.70 (catch at least 70% of rain events)
- ✅ F1-Score > 0.70 (balanced performance)
- ✅ ROC-AUC > 0.80 (strong discrimination)

**Why These Criteria?**:

- **Recall > 0.70**: Don't miss rain events (important for user trust)
- **Precision > 0.70**: Minimize false alarms (avoid "crying wolf")
- **F1 > 0.70**: Balance between recall and precision

### Regression (Rainfall Intensity)

**Target Criteria**:

- ✅ MAE < 2mm/hour for 3-hour forecasts
- ✅ RMSE < 3mm/hour for 3-hour forecasts
- ✅ Beat NEA by >10% (if NEA data available)
- ✅ R² > 0.70 (explain at least 70% of variance)

**Why These Criteria?**:

- **MAE < 2mm/h**: Practical accuracy for user decisions
- **Beat NEA by >10%**: Demonstrate value over official forecast
- **R² > 0.70**: Model captures most rainfall patterns

---

## 9. Recommendations

### Model Strengths (Expected)

- ✅ Good performance for short-term forecasts (1-3 hours)
- ✅ Feature engineering captures important meteorological patterns
- ✅ Cross-validation shows stable performance across time periods
- ✅ Beats naive baselines (persistence, climatology)

### Areas for Improvement (Expected)

- ⚠️ Longer forecast horizons (12-24h) show degraded performance (expected)
- ⚠️ Sudden convective thunderstorms are harder to predict
- ⚠️ Inter-monsoon periods show lower accuracy

### Potential Enhancements

1. **Ensemble Methods**:

   - Combine multiple models (Prophet + XGBoost + LSTM)
   - Weighted averaging based on recent performance

2. **Additional Features**:

   - Radar data (precipitation intensity, movement)
   - Satellite imagery (cloud patterns, temperature)
   - Regional weather patterns (Sumatra, Malaysia)

3. **Continuous Learning**:

   - Daily updates with actual weather data
   - Weekly retraining with new data
   - Adaptive learning rates

4. **Specialized Models**:
   - Separate models for monsoon vs inter-monsoon
   - Separate models for light rain vs heavy rain
   - Time-of-day specific models

---

## 10. Next Steps

### Task 5.3: Create Historical Data Visualization Page

- Display training data overview
- Show year-over-year patterns
- Display time series decomposition
- Show autocorrelation and frequency analysis

### Task 5.4: Integrate ML Predictions into UI

- Display rainfall probability
- Display rainfall intensity
- Show confidence intervals
- Add source indicator ("🤖 ML Model" vs "🌐 Open-Meteo")

### Task 5.5: Create ML Model Performance Dashboard

- Display current model stats
- Show accuracy metrics with explanations
- Display model version history
- Show forward-looking performance

### Task 5.6: Implement Continuous Learning Pipeline

- Daily updates: Fetch actual weather data
- Compare predictions vs actuals
- Weekly retraining: Update models with new data
- Validate: NO mock data in training batches

### Task 5.7: Add ML Model Monitoring and Validation

- Model versioning system
- Model comparison system
- Performance monitoring
- Data validation pipeline

### Task 5.8: Store ML Predictions for Retrospective Evaluation

- Prediction storage
- Actual outcome storage
- Version-specific performance tracking
- Retrospective analysis

---

## Appendix: Evaluation Framework

### Evaluation Script

**Location**: `lionweather/backend/ml/evaluate_rainfall_models.py`

**Usage**:

```bash
cd lionweather/backend
python3 ml/evaluate_rainfall_models.py
```

**Output**:

- `ML_MODEL_PERFORMANCE_RAINFALL.md`: This report (updated with actual metrics)
- `evaluation_plots/`: Diagnostic plots (residuals, Q-Q, scatter)
- Console output: Summary tables and metrics

### Dependencies

**Required**:

- `prophet`: Time series forecasting
- `scikit-learn`: Metrics and cross-validation
- `pandas`: Data manipulation
- `numpy`: Numerical operations
- `matplotlib`: Plotting
- `seaborn`: Statistical visualization
- `scipy`: Statistical tests

**Installation**:

```bash
pip install prophet scikit-learn pandas numpy matplotlib seaborn scipy
```

---

**Report Framework Created**: 2025-03-08
**Models**: Prophet Rainfall Classifier + Regressor
**Training Data**: 2-3 years of historical Singapore weather data
**Validation**: TimeSeriesSplit (5-fold temporal cross-validation)

**Status**: ⏳ Awaiting model training. Once models are trained, run `evaluate_rainfall_models.py` to generate the full report with actual metrics.
