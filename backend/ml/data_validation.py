"""Data validation utilities for ML training pipeline.

This module ensures zero tolerance for mock/synthetic data in training.
All data must come from real API calls with proper validation.
"""

import pandas as pd
from typing import Tuple, List


def detect_mock_data(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Detect mock or synthetic data patterns in training dataset.
    
    Returns:
        Tuple of (is_mock, reasons) where is_mock is True if mock data detected,
        and reasons is a list of specific issues found.
    """
    reasons = []
    
    # Check 1: Source API contains mock/fake/test keywords
    if 'source_api' in df.columns:
        mock_sources = df[df['source_api'].str.contains(
            'mock|fake|test', 
            case=False, 
            na=False
        )]
        if len(mock_sources) > 0:
            reasons.append(
                f"Found {len(mock_sources)} observations with mock/fake/test in source_api"
            )
    
    # Check 2: Suspicious patterns - consecutive identical non-zero values
    numeric_cols = ['temperature', 'rainfall', 'humidity', 'wind_speed', 'pressure']
    
    for col in numeric_cols:
        if col not in df.columns:
            continue
            
        # Check for long runs of identical non-zero values
        values = df[col].values
        if len(values) < 100:
            continue
            
        max_consecutive = 1
        current_consecutive = 1
        
        for i in range(1, len(values)):
            if values[i] == values[i-1] and values[i] != 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1
        
        if max_consecutive > 100:
            reasons.append(
                f"Column '{col}' has {max_consecutive} consecutive identical "
                f"non-zero values (threshold: 100)"
            )
    
    # Check 3: All values are exactly the same (except zeros)
    for col in numeric_cols:
        if col not in df.columns:
            continue
            
        non_zero = df[df[col] != 0][col]
        if len(non_zero) > 10:
            unique_values = non_zero.nunique()
            if unique_values == 1:
                reasons.append(
                    f"Column '{col}' has only one unique non-zero value "
                    f"across {len(non_zero)} observations"
                )
    
    # Check 4: Unrealistic value ranges
    if 'temperature' in df.columns:
        temp_min = df['temperature'].min()
        temp_max = df['temperature'].max()
        # Singapore temperature typically 24-34°C
        if temp_min < 10 or temp_max > 45:
            reasons.append(
                f"Temperature range ({temp_min:.1f} to {temp_max:.1f}°C) "
                f"is unrealistic for Singapore"
            )
    
    if 'humidity' in df.columns:
        humidity_min = df['humidity'].min()
        humidity_max = df['humidity'].max()
        if humidity_min < 0 or humidity_max > 100:
            reasons.append(
                f"Humidity range ({humidity_min:.1f} to {humidity_max:.1f}%) "
                f"is invalid (must be 0-100%)"
            )
    
    if 'rainfall' in df.columns:
        rainfall_max = df['rainfall'].max()
        if rainfall_max > 200:
            reasons.append(
                f"Maximum rainfall ({rainfall_max:.1f} mm/hr) is unrealistic "
                f"(Singapore record is ~150 mm/hr)"
            )
    
    is_mock = len(reasons) > 0
    return is_mock, reasons


def validate_training_data(df: pd.DataFrame) -> None:
    """
    Validate training data and abort if mock data detected.
    
    Raises:
        ValueError: If mock or synthetic data is detected
    """
    is_mock, reasons = detect_mock_data(df)
    
    if is_mock:
        error_report = "\n".join([
            "=" * 80,
            "MOCK DATA DETECTED - TRAINING ABORTED",
            "=" * 80,
            "",
            "Zero tolerance policy: All training data must come from real API calls.",
            "",
            "Issues found:",
            ""
        ])
        
        for i, reason in enumerate(reasons, 1):
            error_report += f"{i}. {reason}\n"
        
        error_report += "\n" + "=" * 80
        
        raise ValueError(error_report)
    
    print("✓ Data validation passed: No mock data detected")


def check_data_completeness(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Check if training data has sufficient completeness.
    
    Returns:
        Tuple of (is_complete, warnings) where is_complete is True if data
        meets minimum requirements, and warnings is a list of issues.
    """
    warnings = []
    
    # Check minimum sample size
    if len(df) < 1000:
        warnings.append(
            f"Dataset has only {len(df)} observations (minimum: 1000)"
        )
    
    # Check for required columns
    required_cols = [
        'timestamp', 'temperature', 'rainfall', 'humidity', 
        'wind_speed', 'pressure'
    ]
    
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        warnings.append(
            f"Missing required columns: {', '.join(missing_cols)}"
        )
    
    # Check for excessive missing values
    for col in required_cols:
        if col not in df.columns:
            continue
            
        missing_pct = (df[col].isna().sum() / len(df)) * 100
        if missing_pct > 20:
            warnings.append(
                f"Column '{col}' has {missing_pct:.1f}% missing values "
                f"(threshold: 20%)"
            )
    
    is_complete = len(warnings) == 0
    return is_complete, warnings
