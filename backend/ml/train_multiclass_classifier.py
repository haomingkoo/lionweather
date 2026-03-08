"""Train XGBoost multi-class classifier for NEA rainfall FORECASTING.

This model FORECASTS rainfall N hours ahead (not current conditions).
Trains separate models for 1h, 3h, 6h, 12h, and 24h forecast horizons.

Conservative bias:
- Predicting rain when there's none is less harmful (false positive)
- Missing actual rain is more harmful (false negative)
"""

import pandas as pd
import numpy as np
import joblib
from datetime import datetime
from xgboost import XGBClassifier
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    confusion_matrix, classification_report
)
from ml.prepare_training_data import prepare_training_dataset
from ml.temporal_validation import (
    split_train_val_temporal, get_stratified_sample_weights
)
from ml.feature_engineer import get_feature_columns
from ml.nea_classification import NEA_CLASS_NAMES
from ml.create_forecast_targets import create_forecast_dataset, print_forecast_summary


def train_multiclass_classifier(df: pd.DataFrame,
                                forecast_horizon: int = 3,
                                output_path: str = "ml/models/multiclass_classifier_v2_{horizon}h.pkl"):
    """
    Train XGBoost multi-class classifier for NEA rainfall FORECASTING.
    
    Args:
        df: Prepared training dataset with features and current labels
        forecast_horizon: Hours ahead to forecast (1, 3, 6, 12, or 24)
        output_path: Path to save trained model
        
    Returns:
        Trained XGBClassifier model
    """
    print("=" * 80)
    print(f"TRAINING MULTI-CLASS RAINFALL FORECASTER ({forecast_horizon}H AHEAD)")
    print("=" * 80)
    print()
    
    # Create forecast dataset (shift targets forward by forecast_horizon)
    print(f"Creating forecast dataset for {forecast_horizon}h ahead...")
    forecast_datasets = create_forecast_dataset(df, forecast_horizons=[forecast_horizon])
    df_forecast = forecast_datasets[forecast_horizon]
    
    # Update output path with horizon
    output_path = output_path.replace('{horizon}', str(forecast_horizon))
    print()
    
    # Get feature columns
    feature_cols = get_feature_columns()
    
    # Filter for available features
    available_features = [col for col in feature_cols if col in df.columns]
    print(f"Using {len(available_features)} features:")
    for feat in available_features:
        print(f"  - {feat}")
    print()
    
    # Prepare features and TARGET labels (future rainfall)
    X = df_forecast[available_features].values
    y = df_forecast['target_rainfall_class'].values.astype(int)  # FUTURE rainfall, not current!
    
    # Temporal train/validation split
    print("Creating temporal train/validation split...")
    train_df, val_df = split_train_val_temporal(df_forecast, val_fraction=0.2)
    
    X_train = train_df[available_features].values
    y_train = train_df['target_rainfall_class'].values.astype(int)
    X_val = val_df[available_features].values
    y_val = val_df['target_rainfall_class'].values.astype(int)
    
    print()
    
    # Calculate sample weights for conservative prediction
    # Higher weight for rain classes to avoid missing rain
    print("Calculating sample weights (conservative bias)...")
    sample_weights = get_stratified_sample_weights(y_train)
    print()
    
    # Train XGBoost classifier
    print("Training XGBoost multi-class classifier...")
    
    # XGBoost requires consecutive class labels starting from 0
    # Map actual classes to consecutive indices
    unique_classes = np.unique(y_train)
    n_classes = len(unique_classes)
    class_mapping = {old_class: new_class for new_class, old_class in enumerate(unique_classes)}
    reverse_mapping = {new_class: old_class for old_class, new_class in class_mapping.items()}
    
    print(f"Class mapping (NEA class -> model class):")
    for nea_class, model_class in class_mapping.items():
        print(f"  {nea_class} ({NEA_CLASS_NAMES[nea_class]}) -> {model_class}")
    print()
    
    # Remap classes
    y_train_mapped = np.array([class_mapping[c] for c in y_train])
    y_val_mapped = np.array([class_mapping[c] for c in y_val])
    
    print("Hyperparameters:")
    print(f"  - n_estimators: 200")
    print(f"  - max_depth: 6")
    print(f"  - learning_rate: 0.1")
    print(f"  - objective: multi:softprob ({n_classes} classes)")
    print(f"  - eval_metric: mlogloss")
    print()
    
    model = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        objective='multi:softprob',
        eval_metric='mlogloss',
        random_state=42,
        n_jobs=-1
    )
    
    # Train with sample weights
    model.fit(
        X_train, y_train_mapped,
        sample_weight=sample_weights,
        eval_set=[(X_val, y_val_mapped)],
        verbose=False
    )
    
    print("✓ Training complete")
    print()
    
    # Evaluate on validation set
    print("=" * 80)
    print("VALIDATION PERFORMANCE")
    print("=" * 80)
    print()
    
    y_pred_mapped = model.predict(X_val)
    y_pred_proba = model.predict_proba(X_val)
    
    # Remap predictions back to NEA classes
    y_pred = np.array([reverse_mapping[c] for c in y_pred_mapped])
    
    # Overall metrics
    accuracy = accuracy_score(y_val, y_pred)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_val, y_pred, average='weighted', zero_division=0
    )
    
    print(f"Overall Accuracy: {accuracy:.3f}")
    print(f"Weighted Precision: {precision:.3f}")
    print(f"Weighted Recall: {recall:.3f}")
    print(f"Weighted F1-Score: {f1:.3f}")
    print()
    
    # Per-class metrics
    print("Per-Class Performance:")
    precision_per_class, recall_per_class, f1_per_class, support_per_class = \
        precision_recall_fscore_support(y_val, y_pred, average=None, zero_division=0)
    
    for class_id in range(6):
        if class_id in y_val:
            class_name = NEA_CLASS_NAMES[class_id]
            print(f"  Class {class_id} ({class_name}):")
            print(f"    Precision: {precision_per_class[class_id]:.3f}")
            print(f"    Recall:    {recall_per_class[class_id]:.3f}")
            print(f"    F1-Score:  {f1_per_class[class_id]:.3f}")
            print(f"    Support:   {support_per_class[class_id]}")
    print()
    
    # Confusion matrix
    print("Confusion Matrix:")
    cm = confusion_matrix(y_val, y_pred)
    print("     Predicted:")
    print("       ", end="")
    for i in range(6):
        print(f"{i:5d}", end="")
    print()
    print("Actual:")
    for i in range(6):
        print(f"  {i}:  ", end="")
        for j in range(6):
            print(f"{cm[i][j]:5d}", end="")
        print()
    print()
    
    # Feature importance
    print("Top 10 Most Important Features:")
    feature_importance = model.feature_importances_
    feature_names = available_features
    importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': feature_importance
    }).sort_values('importance', ascending=False)
    
    for idx, row in importance_df.head(10).iterrows():
        print(f"  {row['feature']:30s}: {row['importance']:.4f}")
    print()
    
    # Save model with class mapping
    print(f"Saving model to {output_path}...")
    model_data = {
        'model': model,
        'class_mapping': class_mapping,
        'reverse_mapping': reverse_mapping,
        'feature_names': available_features
    }
    joblib.dump(model_data, output_path)
    print("✓ Model saved")
    print()
    
    # Save metadata
    metadata = {
        'model_type': 'XGBClassifier',
        'forecast_horizon_hours': forecast_horizon,
        'n_classes': len(unique_classes),
        'class_mapping': {int(k): int(v) for k, v in class_mapping.items()},
        'features': available_features,
        'training_samples': len(X_train),
        'validation_samples': len(X_val),
        'accuracy': float(accuracy),
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1),
        'training_date': datetime.now().isoformat(),
        'version': 'v2.0.0_nea_aligned_forecast'
    }
    
    metadata_path = output_path.replace('.pkl', '_metadata.json')
    import json
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Metadata saved to {metadata_path}")
    
    return model


if __name__ == "__main__":
    # Prepare training data
    print("Preparing training dataset...")
    df = prepare_training_dataset(country="singapore")
    print()
    
    # Train models for multiple forecast horizons
    for horizon in [1, 3, 6]:
        print()
        model = train_multiclass_classifier(df, forecast_horizon=horizon)
        print()
    
    print()
    print("=" * 80)
    print("MULTI-CLASS FORECAST TRAINING COMPLETE")
    print("Trained models for 1h, 3h, and 6h ahead forecasts")
    print("=" * 80)
