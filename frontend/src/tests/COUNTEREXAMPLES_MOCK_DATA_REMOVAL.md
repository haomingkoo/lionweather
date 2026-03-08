# Counterexamples: Mock Data Usage in LionWeather

**Test Run Date:** 2024
**Test File:** `test_mock_data_removal_exploration.test.jsx`
**Status:** ✅ Bug Confirmed - All tests failed as expected on unfixed code

## Summary

The bug condition exploration test successfully detected **ALL instances of mock data usage** in the LionWeather application. The test failures confirm that the application is displaying fake/hardcoded data instead of real API data in multiple locations.

## Counterexamples Found

### 1. getMockTemperature() Called 27 Times in DetailedWeatherCard ❌

**Test:** `should NOT call getMockTemperature() for main temperature display`

**Expected Behavior:** Temperature should come from `location.weather.temperature` (real API data)

**Actual Behavior:** `getMockTemperature()` was called **27 times** with "Partly Cloudy" condition

**Impact:**

- Main temperature display uses hardcoded value based on weather condition
- Hourly forecast temperatures use mock values with random variations
- Daily forecast temperatures use mock values as fallback

**Evidence:**

```
AssertionError: expected "getMockTemperature" to not be called at all,
but actually been called 27 times

1st-27th getMockTemperature call:
  Array [
    "Partly Cloudy",
  ]
```

**Root Cause:**

- Line in `DetailedWeatherCard.jsx`: `const temperature = getMockTemperature(location.weather.condition);`
- Hourly forecast: `temperature: parseInt(getMockTemperature(location.weather.condition)) + Math.floor(Math.random() * 6) - 3`
- Daily forecast high: `high: day.temperature?.high || parseInt(getMockTemperature(location.weather.condition)) + 2`
- Daily forecast low: `low: day.temperature?.low || parseInt(getMockTemperature(location.weather.condition)) - 6`

---

### 2. getMockTemperature() Called in LocationList ❌

**Test:** `should NOT call getMockTemperature() in LocationList`

**Expected Behavior:** Temperature should come from `location.weather.temperature` (real API data)

**Actual Behavior:** `getMockTemperature()` was called **1 time** for the location

**Impact:** Location list displays hardcoded temperature values instead of real data from 2-hour nowcast API

**Evidence:**

```
AssertionError: expected "getMockTemperature" to not be called at all,
but actually been called 1 times

1st getMockTemperature call:
  Array [
    "Partly Cloudy",
  ]
```

**Root Cause:**

- Line in `LocationList.jsx`: `const temperature = getMockTemperature(location.weather.condition);`

---

### 3. No Error Message Displayed When API Fails ❌

**Test:** `should NOT call generateMockForecasts() when API fails - should display error message`

**Expected Behavior:** When API fails, display error message "Unable to refresh weather data"

**Actual Behavior:** No error message displayed; system silently falls back to `generateMockForecasts()`

**Impact:** Users are shown fake data without knowing the API failed, undermining trust

**Evidence:**

```
Error: expect(received).toBeInTheDocument()

received value must be an HTMLElement or an SVGElement.
Received has type:  Null
Received has value: null
```

**Root Cause:**

- Catch block in `DetailedWeatherCard.jsx`: `catch (err) { generateMockForecasts(); }`
- Comment says: "Silently handle error - fall back to mock data"
- No error state or error message display implemented

---

### 4. Hardcoded Sunrise Time "7:00 AM" ❌

**Test:** `should calculate actual sunrise time for Singapore, not display hardcoded '7:00 AM'`

**Expected Behavior:** Sunrise time should be calculated for Singapore (1.3521°N, 103.8198°E) based on current date

**Actual Behavior:** Hardcoded value "7:00 AM" is displayed

**Impact:** Inaccurate sunrise time shown to users (actual sunrise varies throughout the year: ~6:50 AM to ~7:20 AM)

**Evidence:**

```
Error: expect(element).not.toBeInTheDocument()

expected document not to contain element, found <div
  class="text-2xl xl:text-2xl 2xl:text-2xl font-light text-slate-900"
>
  7:00 AM
</div> instead
```

**Root Cause:**

- Hardcoded in `DetailedWeatherCard.jsx` sunrise card: `7:00 AM`

---

### 5. Hardcoded Sunset Time "7:15 PM" ❌

**Test:** `should calculate actual sunset time for Singapore, not display hardcoded '7:15 PM'`

**Expected Behavior:** Sunset time should be calculated for Singapore (1.3521°N, 103.8198°E) based on current date

**Actual Behavior:** Hardcoded value "7:15 PM" is displayed

**Impact:** Inaccurate sunset time shown to users (actual sunset varies throughout the year: ~6:50 PM to ~7:20 PM)

**Evidence:**

```
Error: expect(element).not.toBeInTheDocument()

expected document not to contain element, found <div
  class="text-2xl xl:text-2xl 2xl:text-2xl font-light text-slate-900"
>
  7:15 PM
</div> instead
```

**Root Cause:**

- Hardcoded in `DetailedWeatherCard.jsx` sunset card: `7:15 PM`

---

### 6. Visibility Card with Hardcoded "10 km" Value ❌

**Test:** `should NOT display visibility card with hardcoded '10 km' value`

**Expected Behavior:** Visibility card should NOT be displayed (NEA doesn't provide visibility data)

**Actual Behavior:** Visibility card is displayed with hardcoded "10 km" value

**Impact:** Users see fake visibility data that never changes, regardless of actual conditions

**Evidence:**

```
Error: expect(element).not.toBeInTheDocument()

expected document not to contain element, found <span
  class="text-xs text-slate-600 uppercase tracking-wide"
>
  Visibility
</span> instead
```

**Root Cause:**

- Hardcoded in `DetailedWeatherCard.jsx` visibility card: `<div>10</div> <span>km</span>`
- NEA APIs do not provide visibility data, so this card should not exist

---

### 7. Pressure Card with Hardcoded "1013 hPa" Value ❌

**Test:** `should NOT display pressure card with hardcoded '1013 hPa' value`

**Expected Behavior:** Pressure card should NOT be displayed (NEA doesn't provide pressure data)

**Actual Behavior:** Pressure card is displayed with hardcoded "1013 hPa" value

**Impact:** Users see fake pressure data that never changes (1013 hPa is standard sea level pressure)

**Evidence:**

```
Error: expect(element).not.toBeInTheDocument()

expected document not to contain element, found <span
  class="text-xs text-slate-600 uppercase tracking-wide"
>
  Pressure
</span> instead
```

**Root Cause:**

- Hardcoded in `DetailedWeatherCard.jsx` pressure card: `<div>1013</div> <span>hPa</span>`
- NEA APIs do not provide pressure data, so this card should not exist

---

### 8. Comprehensive Mock Data Detection Summary ❌

**Test:** `should detect all instances of mock data usage in the application`

**Expected Behavior:** No mock data issues should be found

**Actual Behavior:** **5 distinct mock data issues detected**

**Evidence:**

```
AssertionError: expected [ …(5) ] to have a length of +0 but got 5

=== COUNTEREXAMPLES FOUND ===
Mock data issues detected:
1. getMockTemperature() called 27 times
2. Hardcoded sunrise time '7:00 AM' found
3. Hardcoded sunset time '7:15 PM' found
4. Visibility card displayed (NEA doesn't provide this data)
5. Pressure card displayed (NEA doesn't provide this data)
=============================
```

---

## Additional Findings

### Daily Forecast Length (Passed Unexpectedly) ✅

**Test:** `should display maximum 4 days of forecast, not 10 days`

**Expected:** Test should FAIL (showing 10 days)

**Actual:** Test PASSED (showing 4 days or fewer)

**Analysis:** The mock API in the test returns only 4 days of forecast data, so the component correctly displays 4 days. However, the code still has the logic to generate 10 days in the `generateMockForecasts()` function:

```javascript
const daily = Array.from({ length: 10 }, (_, i) => {
  // ... generates 10 days of fake data
});
```

This means when the API fails, the system would generate 10 days of fake data. The test passed because we mocked successful API responses with 4 days.

---

## Validation Against Requirements

| Requirement                              | Status     | Counterexample                               |
| ---------------------------------------- | ---------- | -------------------------------------------- |
| 2.1 - Main temperature uses real data    | ❌ FAILED  | getMockTemperature() called 27 times         |
| 2.2 - Hourly forecast uses real data     | ❌ FAILED  | Mock temperature with random variation       |
| 2.3 - Daily forecast limited to 4 days   | ⚠️ PARTIAL | Code has 10-day generation in error path     |
| 2.4 - API failures show error messages   | ❌ FAILED  | Silent fallback to mock data                 |
| 2.5 - No visibility/pressure cards       | ❌ FAILED  | Both cards displayed with hardcoded values   |
| 2.6 - Sunrise time calculated            | ❌ FAILED  | Hardcoded "7:00 AM"                          |
| 2.7 - Sunset time calculated             | ❌ FAILED  | Hardcoded "7:15 PM"                          |
| 2.8 - LocationList uses real temperature | ❌ FAILED  | getMockTemperature() called                  |
| 2.9 - getMockTemperature() removed       | ❌ FAILED  | Function exists and is called 28 times total |

---

## Conclusion

The bug condition exploration test successfully confirmed that **ALL identified mock data issues exist in the unfixed code**. The test failures provide clear evidence that:

1. ✅ `getMockTemperature()` is being used extensively (28 total calls)
2. ✅ Hardcoded sunrise/sunset times are displayed
3. ✅ Visibility and pressure cards show fake data
4. ✅ API failures result in silent fallback to mock data (no error messages)
5. ✅ Code contains logic to generate 10 days of fake forecast data

**Next Steps:**

1. Implement the fix as specified in the design document
2. Re-run this same test to verify it passes after the fix
3. Ensure all mock data is removed and only real API data is displayed

**Test Status:** ✅ **SUCCESSFUL EXPLORATION** - All expected failures occurred, confirming the bug exists
