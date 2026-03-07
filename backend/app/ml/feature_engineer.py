"""
Feature Engineering Service for ML Weather Forecasting

This module provides feature engineering capabilities for weather data,
including temporal features, lag features, rolling statistics, and normalization.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime


class FeatureEngineer:
    """
    Feature engineering service for weather forecasting models.
    
    Provides methods to create:
    - Temporal features (hour, day_of_week, month, season, is_weekend)
    - Lag features (previous values at t-1, t-3, t-7)
    - Rolling statistics (7-day and 30-day windows)
    - Feature normalization (zero mean, unit variance)
    """
    
    def __init__(self):
        """Initialize the FeatureEngineer."""
        self.scaler_params = {}
    
    def create_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create temporal features from timestamp column.
        
        Extracts the following features:
        - hour: Hour of day (0-23)
        - day_of_week: Day of week (0-6, Monday=0, Sunday=6)
        - month: Month of year (1-12)
        - season: Season derived from month (0=winter, 1=spring, 2=summer, 3=fall)
        - is_weekend: Boolean indicating weekend (True for Saturday/Sunday)
        
        Args:
            df: DataFrame with a 'timestamp' column (datetime or string)
        
        Returns:
            DataFrame with added temporal feature columns
        
        Requirements:
            - Validates Requirements 13.3, 13.4
            - Property 42: Temporal Feature Extraction
        """
        # Make a copy to avoid modifying the original
        df = df.copy()
        
        # Ensure timestamp is datetime type
        if 'timestamp' not in df.columns:
            raise ValueError("DataFrame must contain a 'timestamp' column")
        
        # Convert timestamp to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Extract hour (0-23)
        df['hour'] = df['timestamp'].dt.hour
        
        # Extract day of week (0-6, Monday=0, Sunday=6)
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        
        # Extract month (1-12)
        df['month'] = df['timestamp'].dt.month
        
        # Calculate season from month
        # Winter: Dec(12), Jan(1), Feb(2) -> 0
        # Spring: Mar(3), Apr(4), May(5) -> 1
        # Summer: Jun(6), Jul(7), Aug(8) -> 2
        # Fall: Sep(9), Oct(10), Nov(11) -> 3
        df['season'] = df['month'].apply(self._month_to_season)
        
        # Calculate is_weekend (Saturday=5, Sunday=6)
        df['is_weekend'] = df['day_of_week'].isin([5, 6])
        
        return df
    
    @staticmethod
    def _month_to_season(month: int) -> int:
        """
        Convert month to season.
        
        Args:
            month: Month number (1-12)
        
        Returns:
            Season number (0=winter, 1=spring, 2=summer, 3=fall)
        """
        if month in [12, 1, 2]:
            return 0  # Winter
        elif month in [3, 4, 5]:
            return 1  # Spring
        elif month in [6, 7, 8]:
            return 2  # Summer
        else:  # month in [9, 10, 11]
            return 3  # Fall

    def create_lag_features(self, df: pd.DataFrame, columns: List[str],
                           lags: List[int] = [1, 3, 7]) -> pd.DataFrame:
        """
        Create lagged versions of specified columns.

        For each column and lag value, creates a new column containing the value
        from 'lag' time steps ago. This helps models understand temporal dependencies
        by providing access to historical values.

        Args:
            df: DataFrame with time-ordered data
            columns: List of column names to create lag features for
            lags: List of lag values (default: [1, 3, 7] for t-1, t-3, t-7)

        Returns:
            DataFrame with added lag feature columns named {column}_lag_{lag}

        Requirements:
            - Validates Requirements 13.5
            - Property 43: Lag Feature Correctness
        """
        df = df.copy()
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Columns not found in DataFrame: {missing_cols}")

        for col in columns:
            for lag in lags:
                lag_col_name = f"{col}_lag_{lag}"
                df[lag_col_name] = df[col].shift(lag)

        return df

    def create_rolling_features(self, df: pd.DataFrame, columns: List[str],
                               windows: List[int] = [7, 30]) -> pd.DataFrame:
        """
        Create rolling statistics (mean, std, min, max) for specified columns.

        For each column and window size, calculates rolling statistics over the
        specified window. This helps models understand trends and variability
        over different time horizons.

        Args:
            df: DataFrame with time-ordered data
            columns: List of column names to create rolling features for
            windows: List of window sizes in time steps (default: [7, 30] for 7-day and 30-day)

        Returns:
            DataFrame with added rolling feature columns

        Requirements:
            - Validates Requirements 13.1, 13.2
            - Property 41: Rolling Average Calculation
        """
        df = df.copy()
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Columns not found in DataFrame: {missing_cols}")

        for col in columns:
            for window in windows:
                rolling = df[col].rolling(window=window, min_periods=1)
                df[f"{col}_rolling_mean_{window}"] = rolling.mean()
                df[f"{col}_rolling_std_{window}"] = rolling.std()
                df[f"{col}_rolling_min_{window}"] = rolling.min()
                df[f"{col}_rolling_max_{window}"] = rolling.max()

        return df

    def create_lag_features(self, df: pd.DataFrame, columns: List[str],
                           lags: List[int] = [1, 3, 7]) -> pd.DataFrame:
        """
        Create lagged versions of specified columns.

        For each column and lag value, creates a new column containing the value
        from 'lag' time steps ago. This helps models understand temporal dependencies
        by providing access to historical values.

        Args:
            df: DataFrame with time-ordered data
            columns: List of column names to create lag features for
            lags: List of lag values (default: [1, 3, 7] for t-1, t-3, t-7)

        Returns:
            DataFrame with added lag feature columns named {column}_lag_{lag}

        Example:
            If df has a 'temperature' column with values [20, 21, 22, 23, 24],
            create_lag_features(df, ['temperature'], [1, 2]) will add:
            - temperature_lag_1: [NaN, 20, 21, 22, 23]
            - temperature_lag_2: [NaN, NaN, 20, 21, 22]

        Requirements:
            - Validates Requirements 13.5
            - Property 43: Lag Feature Correctness
        """
        # Make a copy to avoid modifying the original
        df = df.copy()

        # Validate that all specified columns exist
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Columns not found in DataFrame: {missing_cols}")

        # Create lag features for each column and lag value
        for col in columns:
            for lag in lags:
                # Create column name: e.g., temperature_lag_1
                lag_col_name = f"{col}_lag_{lag}"

                # Shift the column by 'lag' positions
                # shift(1) moves values down by 1, so index 1 gets value from index 0
                df[lag_col_name] = df[col].shift(lag)

        return df

    def create_rolling_features(self, df: pd.DataFrame, columns: List[str],
                               windows: List[int] = [7, 30]) -> pd.DataFrame:
        """
        Create rolling statistics (mean, std, min, max) for specified columns.

        For each column and window size, calculates rolling statistics over the
        specified window. This helps models understand trends and variability
        over different time horizons.

        Args:
            df: DataFrame with time-ordered data
            columns: List of column names to create rolling features for
            windows: List of window sizes in time steps (default: [7, 30] for 7-day and 30-day)

        Returns:
            DataFrame with added rolling feature columns named:
            - {column}_rolling_mean_{window}
            - {column}_rolling_std_{window}
            - {column}_rolling_min_{window}
            - {column}_rolling_max_{window}

        Example:
            If df has a 'temperature' column, create_rolling_features(df, ['temperature'], [3])
            will add columns for 3-period rolling mean, std, min, and max.

        Requirements:
            - Validates Requirements 13.1, 13.2
            - Property 41: Rolling Average Calculation
        """
        # Make a copy to avoid modifying the original
        df = df.copy()

        # Validate that all specified columns exist
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Columns not found in DataFrame: {missing_cols}")

        # Create rolling features for each column and window size
        for col in columns:
            for window in windows:
                # Calculate rolling statistics
                # min_periods=1 allows calculation even with fewer than 'window' values
                rolling = df[col].rolling(window=window, min_periods=1)

                # Create feature columns
                df[f"{col}_rolling_mean_{window}"] = rolling.mean()
                df[f"{col}_rolling_std_{window}"] = rolling.std()
                df[f"{col}_rolling_min_{window}"] = rolling.min()
                df[f"{col}_rolling_max_{window}"] = rolling.max()

        return df

    def normalize_features(self, df: pd.DataFrame, columns: List[str],
                          fit: bool = True) -> pd.DataFrame:
        """
        Normalize features using StandardScaler (zero mean, unit variance).

        Args:
            df: DataFrame with features to normalize
            columns: List of column names to normalize
            fit: If True, fit scaler on data and store parameters. If False, use stored parameters.

        Returns:
            DataFrame with normalized features

        Requirements:
            - Validates Requirements 13.6
            - Property 44: Feature Normalization
        """
        df = df.copy()
        
        for col in columns:
            if col not in df.columns:
                raise ValueError(f"Column {col} not found in DataFrame")
            
            if fit:
                # Calculate and store mean and std
                mean = df[col].mean()
                std = df[col].std()
                self.scaler_params[col] = {'mean': mean, 'std': std}
            else:
                # Use stored parameters
                if col not in self.scaler_params:
                    raise ValueError(f"No scaler parameters found for column {col}")
                mean = self.scaler_params[col]['mean']
                std = self.scaler_params[col]['std']
            
            # Normalize: (x - mean) / std
            if std > 0:
                df[col] = (df[col] - mean) / std
            else:
                df[col] = 0.0
        
        return df

    def prepare_training_data(self, df: pd.DataFrame,
                             target_columns: List[str],
                             create_lags: bool = True,
                             create_rolling: bool = True,
                             normalize: bool = True) -> pd.DataFrame:
        """
        Prepare training data by applying all feature engineering steps.

        Args:
            df: Raw DataFrame with timestamp and weather data
            target_columns: Columns to create features for (e.g., ['temperature', 'humidity'])
            create_lags: Whether to create lag features
            create_rolling: Whether to create rolling features
            normalize: Whether to normalize features

        Returns:
            DataFrame ready for model training

        Requirements:
            - Validates Requirements 13.1-13.6
        """
        result = df.copy()
        
        # Create temporal features
        result = self.create_temporal_features(result)
        
        # Create lag features
        if create_lags:
            result = self.create_lag_features(result, target_columns)
        
        # Create rolling features
        if create_rolling:
            result = self.create_rolling_features(result, target_columns)
        
        # Normalize features
        if normalize:
            # Get all numeric columns except timestamp
            numeric_cols = result.select_dtypes(include=[np.number]).columns.tolist()
            result = self.normalize_features(result, numeric_cols, fit=True)
        
        return result
