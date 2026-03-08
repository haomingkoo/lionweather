"""Temporal cross-validation for time series ML models.

Ensures strict temporal ordering: training data always precedes validation data.
Zero tolerance for data leakage from future to past.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from typing import List, Tuple, Generator


def verify_temporal_ordering(train_indices: np.ndarray, 
                             val_indices: np.ndarray,
                             timestamps: pd.Series) -> bool:
    """
    Verify that all training timestamps precede all validation timestamps.
    
    Args:
        train_indices: Indices of training samples
        val_indices: Indices of validation samples
        timestamps: Series of timestamps
        
    Returns:
        True if temporal ordering is correct, False otherwise
    """
    train_timestamps = timestamps.iloc[train_indices]
    val_timestamps = timestamps.iloc[val_indices]
    
    max_train_time = train_timestamps.max()
    min_val_time = val_timestamps.min()
    
    # All training data must be before all validation data
    is_valid = max_train_time < min_val_time
    
    if not is_valid:
        print(f"  ✗ TEMPORAL ORDERING VIOLATION:")
        print(f"    Max training time: {max_train_time}")
        print(f"    Min validation time: {min_val_time}")
        print(f"    Overlap: {max_train_time >= min_val_time}")
    
    return is_valid


def create_temporal_splits(df: pd.DataFrame, 
                          n_splits: int = 5) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
    """
    Create temporal cross-validation splits with strict ordering.
    
    Uses TimeSeriesSplit to ensure training data always precedes validation data.
    
    Args:
        df: DataFrame with timestamp column
        n_splits: Number of cross-validation folds
        
    Yields:
        Tuples of (train_indices, val_indices) for each fold
        
    Raises:
        ValueError: If temporal ordering is violated
    """
    if 'timestamp' not in df.columns:
        raise ValueError("DataFrame must have 'timestamp' column")
    
    # Ensure data is sorted by timestamp
    df = df.sort_values('timestamp').reset_index(drop=True)
    timestamps = pd.to_datetime(df['timestamp'])
    
    print(f"Creating {n_splits} temporal cross-validation folds...")
    print(f"Data range: {timestamps.min()} to {timestamps.max()}")
    print()
    
    # Use TimeSeriesSplit for temporal ordering
    tscv = TimeSeriesSplit(n_splits=n_splits)
    
    fold_num = 1
    for train_idx, val_idx in tscv.split(df):
        # Verify temporal ordering
        is_valid = verify_temporal_ordering(train_idx, val_idx, timestamps)
        
        if not is_valid:
            raise ValueError(
                f"Temporal ordering violation in fold {fold_num}. "
                f"Training data must precede validation data."
            )
        
        train_start = timestamps.iloc[train_idx].min()
        train_end = timestamps.iloc[train_idx].max()
        val_start = timestamps.iloc[val_idx].min()
        val_end = timestamps.iloc[val_idx].max()
        
        print(f"Fold {fold_num}:")
        print(f"  Training:   {len(train_idx):6d} samples  ({train_start} to {train_end})")
        print(f"  Validation: {len(val_idx):6d} samples  ({val_start} to {val_end})")
        print(f"  ✓ Temporal ordering verified")
        print()
        
        yield train_idx, val_idx
        fold_num += 1


def split_train_val_temporal(df: pd.DataFrame, 
                             val_fraction: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split data into training and validation sets with temporal ordering.
    
    Simple single split: earliest data for training, latest data for validation.
    
    Args:
        df: DataFrame with timestamp column
        val_fraction: Fraction of data to use for validation (default: 0.2)
        
    Returns:
        Tuple of (train_df, val_df)
        
    Raises:
        ValueError: If temporal ordering is violated
    """
    if 'timestamp' not in df.columns:
        raise ValueError("DataFrame must have 'timestamp' column")
    
    # Ensure data is sorted by timestamp
    df = df.sort_values('timestamp').reset_index(drop=True)
    timestamps = pd.to_datetime(df['timestamp'])
    
    # Calculate split point
    split_idx = int(len(df) * (1 - val_fraction))
    
    train_df = df.iloc[:split_idx].copy()
    val_df = df.iloc[split_idx:].copy()
    
    # Verify temporal ordering
    max_train_time = pd.to_datetime(train_df['timestamp']).max()
    min_val_time = pd.to_datetime(val_df['timestamp']).min()
    
    if max_train_time >= min_val_time:
        raise ValueError(
            f"Temporal ordering violation: "
            f"max training time ({max_train_time}) >= "
            f"min validation time ({min_val_time})"
        )
    
    print("Temporal train/validation split:")
    print(f"  Training:   {len(train_df):6d} samples  "
          f"({train_df['timestamp'].min()} to {train_df['timestamp'].max()})")
    print(f"  Validation: {len(val_df):6d} samples  "
          f"({val_df['timestamp'].min()} to {val_df['timestamp'].max()})")
    print(f"  ✓ Temporal ordering verified")
    
    return train_df, val_df


def get_stratified_sample_weights(y: np.ndarray) -> np.ndarray:
    """
    Calculate sample weights to handle class imbalance.
    
    Important: For rainfall prediction, we want to be more conservative:
    - Predicting rain when there's none is less harmful (false positive)
    - Missing actual rain is more harmful (false negative)
    
    Therefore, we give higher weight to rain classes (1-5) vs no rain (0).
    
    Args:
        y: Array of class labels (0-5)
        
    Returns:
        Array of sample weights
    """
    from sklearn.utils.class_weight import compute_class_weight
    
    # Compute base class weights (inverse frequency)
    classes = np.unique(y)
    base_weights = compute_class_weight('balanced', classes=classes, y=y)
    
    # Create weight dictionary
    class_weights = dict(zip(classes, base_weights))
    
    # Adjust weights: boost rain classes, reduce no-rain class
    # This makes the model more conservative (prefer predicting rain)
    if 0 in class_weights:
        class_weights[0] *= 0.7  # Reduce weight for "No Rain"
    
    for rain_class in [1, 2, 3, 4, 5]:
        if rain_class in class_weights:
            class_weights[rain_class] *= 1.2  # Boost weight for rain classes
    
    # Map weights to samples
    sample_weights = np.array([class_weights[label] for label in y])
    
    print("Class weights (adjusted for conservative prediction):")
    for class_id in sorted(class_weights.keys()):
        print(f"  Class {class_id}: {class_weights[class_id]:.3f}")
    
    return sample_weights
