"""NEA-aligned rainfall classification system.

This module implements Singapore NEA's official 6-class rainfall classification
with thunderstorm detection using meteorological indicators.
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional


# WMO Weather Code to NEA Rainfall Class Mapping
WMO_TO_NEA_CLASS = {
    # Clear/Cloudy (No Rain)
    0: 0, 1: 0, 2: 0, 3: 0,  # Clear to overcast
    
    # Drizzle (Light Showers)
    51: 1, 53: 1, 55: 1,  # Light to dense drizzle
    56: 1, 57: 1,  # Freezing drizzle (rare in Singapore)
    
    # Rain (Moderate to Heavy Showers)
    61: 2, 63: 3, 65: 3,  # Light, moderate, heavy rain
    66: 3, 67: 3,  # Freezing rain (rare)
    
    # Rain Showers (Light to Heavy)
    80: 1, 81: 2, 82: 3,  # Light, moderate, heavy showers
    
    # Thunderstorms (Thundery Showers)
    95: 4, 96: 4, 99: 4,  # Thunderstorm with/without hail
    
    # Snow (Not applicable to Singapore, map to No Rain)
    71: 0, 73: 0, 75: 0, 77: 0, 85: 0, 86: 0,
}


# NEA Rainfall Class Names
NEA_CLASS_NAMES = {
    0: "No Rain",
    1: "Light Showers",
    2: "Moderate Showers",
    3: "Heavy Showers",
    4: "Thundery Showers",
    5: "Very Heavy Rain"
}


def detect_thunderstorm(row: pd.Series) -> float:
    """
    Calculate thunderstorm probability from meteorological indicators.
    
    Indicators:
    1. Pressure drop >3 hPa in 3 hours (weight: 0.15)
    2. High humidity >85% (weight: 0.10)
    3. Afternoon period 14:00-18:00 (weight: 0.20)
    4. Wind direction change >45° in 1 hour (weight: 0.15)
    5. Temperature drop >3°C in 1 hour (weight: 0.15)
    6. Bonus for 3+ indicators (weight: 0.25)
    
    Args:
        row: DataFrame row with thunderstorm indicator features
        
    Returns:
        Thunderstorm probability (0.0-1.0)
    """
    score = 0.0
    indicators_flagged = 0
    
    # Indicator 1: Pressure drop (weight: 0.15)
    if 'pressure_drop_3h' in row and pd.notna(row['pressure_drop_3h']):
        if row['pressure_drop_3h'] > 3:
            score += 0.15
            indicators_flagged += 1
    
    # Indicator 2: High humidity (weight: 0.10)
    if 'humidity' in row and pd.notna(row['humidity']):
        if row['humidity'] > 85:
            score += 0.10
            indicators_flagged += 1
    
    # Indicator 3: Afternoon peak (weight: 0.20)
    if 'afternoon_period' in row and pd.notna(row['afternoon_period']):
        if row['afternoon_period'] == 1:
            score += 0.20
            indicators_flagged += 1
    
    # Indicator 4: Wind direction change (weight: 0.15)
    if 'wind_direction_change_1h' in row and pd.notna(row['wind_direction_change_1h']):
        if row['wind_direction_change_1h'] > 45:
            score += 0.15
            indicators_flagged += 1
    
    # Indicator 5: Temperature drop (weight: 0.15)
    if 'temperature_drop_1h' in row and pd.notna(row['temperature_drop_1h']):
        if row['temperature_drop_1h'] > 3:
            score += 0.15
            indicators_flagged += 1
    
    # Bonus: Multiple indicators (weight: 0.25)
    if indicators_flagged >= 3:
        score += 0.25
    
    return min(score, 1.0)


def classify_rainfall(intensity: float, thunderstorm_prob: float) -> int:
    """
    Classify rainfall into NEA-aligned classes.
    
    Priority:
    1. Thunderstorm detection overrides intensity-based classification
    2. Intensity-based classification for non-thunderstorm conditions
    
    Args:
        intensity: Rainfall intensity in mm/hour
        thunderstorm_prob: Thunderstorm probability (0.0-1.0)
        
    Returns:
        NEA rainfall class ID (0-5)
    """
    # Priority 1: Thunderstorm detection
    if thunderstorm_prob > 0.6 and intensity > 0.5:
        return 4  # Thundery Showers
    
    # Priority 2: Intensity-based classification
    if intensity == 0:
        return 0  # No Rain
    elif intensity < 2:
        return 1  # Light Showers
    elif intensity < 10:
        return 2  # Moderate Showers
    elif intensity < 30:
        return 3  # Heavy Showers
    else:
        return 5  # Very Heavy Rain


def map_wmo_to_nea(wmo_code: Optional[int], intensity: float) -> int:
    """
    Map WMO weather code to NEA rainfall class.
    
    Uses WMO code as primary signal, intensity as secondary refinement.
    
    Args:
        wmo_code: WMO weather code (0-99), or None if not available
        intensity: Rainfall intensity in mm/hour
        
    Returns:
        NEA rainfall class ID (0-5)
    """
    if wmo_code is None or pd.isna(wmo_code):
        # No WMO code, use intensity only
        if intensity == 0:
            return 0
        elif intensity < 2:
            return 1
        elif intensity < 10:
            return 2
        elif intensity < 30:
            return 3
        else:
            return 5
    
    wmo_code = int(wmo_code)
    
    # Thunderstorm codes always map to Thundery Showers
    if wmo_code in [95, 96, 99]:
        return 4
    
    # Use mapping table with intensity refinement
    base_class = WMO_TO_NEA_CLASS.get(wmo_code, 0)
    
    # Refine based on intensity if available
    if intensity > 30:
        return 5  # Very Heavy Rain
    elif intensity > 10 and base_class >= 2:
        return 3  # Heavy Showers
    
    return base_class


def label_training_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Label historical data with NEA rainfall classes.
    
    Uses both rainfall intensity and WMO weather codes.
    Computes thunderstorm probability for each observation.
    
    Args:
        df: DataFrame with weather observations and computed features
        
    Returns:
        DataFrame with added labels:
        - rainfall_class: NEA class ID (0-5)
        - thunderstorm_prob: Thunderstorm probability (0.0-1.0)
        - thunderstorm_present: Binary label (0 or 1)
    """
    df = df.copy()
    
    # Compute thunderstorm probability for each observation
    print("Computing thunderstorm probabilities...")
    df['thunderstorm_prob'] = df.apply(detect_thunderstorm, axis=1)
    
    # Label with NEA class
    print("Assigning NEA rainfall classes...")
    
    def assign_class(row):
        intensity = row.get('rainfall', 0)
        ts_prob = row.get('thunderstorm_prob', 0)
        wmo_code = row.get('weather_code', None)
        
        # Priority 1: WMO thunderstorm codes
        if wmo_code in [95, 96, 99]:
            return 4
        
        # Priority 2: High thunderstorm probability
        if ts_prob > 0.7 and intensity > 0.5:
            return 4
        
        # Priority 3: Intensity-based classification
        if intensity == 0:
            return 0
        elif intensity < 2:
            return 1
        elif intensity < 10:
            return 2
        elif intensity < 30:
            return 3
        else:
            return 5
    
    df['rainfall_class'] = df.apply(assign_class, axis=1)
    
    # Binary thunderstorm label for thunderstorm detector
    df['thunderstorm_present'] = (
        (df['rainfall_class'] == 4) |
        (df['thunderstorm_prob'] > 0.7)
    ).astype(int)
    
    # Print class distribution
    print("\nNEA Rainfall Class Distribution:")
    class_counts = df['rainfall_class'].value_counts().sort_index()
    for class_id, count in class_counts.items():
        class_name = NEA_CLASS_NAMES[class_id]
        pct = (count / len(df)) * 100
        print(f"  Class {class_id} ({class_name}): {count} ({pct:.1f}%)")
    
    print(f"\nThunderstorm observations: {df['thunderstorm_present'].sum()} "
          f"({(df['thunderstorm_present'].sum() / len(df)) * 100:.1f}%)")
    
    return df


def get_class_name(class_id: int) -> str:
    """
    Get NEA rainfall class name from class ID.
    
    Args:
        class_id: NEA class ID (0-5)
        
    Returns:
        Class name string
    """
    return NEA_CLASS_NAMES.get(class_id, "Unknown")


def get_nea_color_code(class_id: int) -> str:
    """
    Get NEA radar color code for rainfall class.
    
    Args:
        class_id: NEA class ID (0-5)
        
    Returns:
        Color description string
    """
    color_codes = {
        0: "White/Clear",
        1: "Light Blue/Green",
        2: "Yellow/Orange",
        3: "Red",
        4: "Purple/White",
        5: "Dark Red/Purple"
    }
    return color_codes.get(class_id, "Unknown")


def get_intensity_range(class_id: int) -> str:
    """
    Get intensity range description for rainfall class.
    
    Args:
        class_id: NEA class ID (0-5)
        
    Returns:
        Intensity range string
    """
    ranges = {
        0: "0 mm/hr",
        1: "0.5-2 mm/hr",
        2: "2-10 mm/hr",
        3: "10-30 mm/hr",
        4: "Variable (with lightning)",
        5: ">30 mm/hr"
    }
    return ranges.get(class_id, "Unknown")
