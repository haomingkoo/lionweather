# Counterexamples for ML Data Leakage Bug (Bug 3)

## Bug Condition Exploration Test Results

**Test File**: `test_ml_data_leakage_exploration.py`

**Status**: Test PASSES on fixed code (fix was already implemented in task 11.1)

**Note**: This document describes the counterexamples that WOULD have been found if the test had been run on UNFIXED code (before task 11.1 implementation).

---

## Counterexample 1: Rolling Mean Includes Current Value at Time t

**Test**: `test_rolling_features_data_leakage_simple_case`

**Input DataFrame**:

```
timestamp           temperature
2024-01-01         20
2024-01-02         21
2024-01-03         22
2024-01-04         23
2024-01-05         24
```

**Window**: 3-period rolling mean

### Expected Behavior (WITH .shift(1) - FIXED CODE):

- Index 0: `rolling_mean_3 = NaN` (no previous values due to shift)
- Index 1: `rolling_mean_3 = 20.0` (uses only [20] from index 0)
- Index 2: `rolling_mean_3 = 20.5` (uses only [20, 21] from indices 0, 1)
- Index 3: `rolling_mean_3 = 21.0` (uses only [20, 21, 22] from indices 0, 1, 2)

### Actual Behavior on UNFIXED Code (WITHOUT .shift(1)):

- Index 0: `rolling_mean_3 = 20.0` ❌ (includes current value at index 0 - DATA LEAKAGE!)
- Index 1: `rolling_mean_3 = 20.5` ❌ (includes current value at index 1 - DATA LEAKAGE!)
- Index 2: `rolling_mean_3 = 21.0` ❌ (includes current value at index 2 - DATA LEAKAGE!)
- Index 3: `rolling_mean_3 = 22.0` ❌ (includes current value at index 3 - DATA LEAKAGE!)

**Counterexample Demonstration**:
At index 2 (time t=2, temperature=22):

- UNFIXED: `rolling_mean = (20 + 21 + 22) / 3 = 21.0` - includes value 22 at time t
- FIXED: `rolling_mean = (20 + 21) / 2 = 20.5` - only uses values from times < t

**Impact**: The rolling mean at time t includes the current temperature value, which is the target we're trying to predict. This violates temporal causality and causes data leakage.

---

## Counterexample 2: Temporal Causality Violation

**Test**: `test_rolling_features_temporal_causality_violation`

**Input DataFrame**:

```
timestamp           temperature
2024-01-01         10
2024-01-02         20
2024-01-03         30
2024-01-04         40
2024-01-05         50
2024-01-06         60
2024-01-07         70
2024-01-08         80
2024-01-09         90
2024-01-10         100
```

**Window**: 3-period rolling mean

### Counterexample at Index 3:

- Time t=3, temperature=40
- UNFIXED: `rolling_mean = (20 + 30 + 40) / 3 = 30.0` ❌
  - Uses values from indices [1, 2, 3] = [20, 30, 40]
  - Includes current value 40 at time t=3
- FIXED: `rolling_mean = (10 + 20 + 30) / 3 = 20.0` ✓
  - Uses values from indices [0, 1, 2] = [10, 20, 30]
  - Only uses values from times < t

### Counterexample at Index 5:

- Time t=5, temperature=60
- UNFIXED: `rolling_mean = (40 + 50 + 60) / 3 = 50.0` ❌
  - Uses values from indices [3, 4, 5] = [40, 50, 60]
  - Includes current value 60 at time t=5
- FIXED: `rolling_mean = (30 + 40 + 50) / 3 = 40.0` ✓
  - Uses values from indices [2, 3, 4] = [30, 40, 50]
  - Only uses values from times < t

**Impact**: The model would be using future data (the current temperature) to predict the future temperature, artificially inflating training accuracy and causing poor generalization.

---

## Counterexample 3: Rolling Min/Max Data Leakage

**Test**: `test_rolling_features_min_max_leakage`

**Input DataFrame**:

```
timestamp           temperature
2024-01-01         15
2024-01-02         10
2024-01-03         25
2024-01-04         20
2024-01-05         30
2024-01-06         5
```

**Window**: 3-period rolling min and max

### Counterexample at Index 4:

- Time t=4, temperature=30
- UNFIXED:
  - `rolling_min = min([25, 20, 30]) = 20` ❌ (includes current value 30)
  - `rolling_max = max([25, 20, 30]) = 30` ❌ (includes current value 30 - DATA LEAKAGE!)
- FIXED:
  - `rolling_min = min([10, 25, 20]) = 10` ✓ (only uses values from times < t)
  - `rolling_max = max([10, 25, 20]) = 25` ✓ (only uses values from times < t)

**Impact**: The rolling max at time t=4 is 30, which is exactly the current temperature value. This means the model has access to the target value it's trying to predict, causing severe data leakage.

---

## Summary of Data Leakage Bug

### Root Cause:

The `create_rolling_features()` method in `feature_engineer.py` did NOT apply `.shift(1)` after calculating rolling statistics:

```python
# UNFIXED CODE (WRONG):
df[f"{col}_rolling_mean_{window}"] = rolling.mean()
df[f"{col}_rolling_std_{window}"] = rolling.std()
df[f"{col}_rolling_min_{window}"] = rolling.min()
df[f"{col}_rolling_max_{window}"] = rolling.max()
```

### Fix Applied in Task 11.1:

```python
# FIXED CODE (CORRECT):
df[f"{col}_rolling_mean_{window}"] = rolling.mean().shift(1)
df[f"{col}_rolling_std_{window}"] = rolling.std().shift(1)
df[f"{col}_rolling_min_{window}"] = rolling.min().shift(1)
df[f"{col}_rolling_max_{window}"] = rolling.max().shift(1)
```

### Impact of Bug:

1. **Temporal Causality Violation**: Rolling features at time t include the value at time t, which is the target we're trying to predict
2. **Inflated Training Accuracy**: Models appear more accurate during training because they have access to future data
3. **Poor Generalization**: Models fail in production because they can't access future data during real-time prediction
4. **Invalid ML Pipeline**: The entire ML pipeline produces unreliable predictions due to data leakage

### Validation:

All three exploration tests now PASS on the fixed code, confirming that:

- Rolling features at index 0 are NaN (due to shift)
- Rolling features at time t only use data from times < t
- Temporal causality is maintained across all rolling statistics (mean, std, min, max)
