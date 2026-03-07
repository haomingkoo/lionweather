"""
Evaluation Service for ML Weather Forecasting

Evaluates model predictions against actual weather data.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class EvaluationMetric:
    """Evaluation metric for a model prediction"""
    model_id: str
    weather_parameter: str
    forecast_horizon: int  # hours ahead
    mae: float
    rmse: float
    mape: float
    evaluated_at: datetime
    country: Optional[str] = None
    location: Optional[str] = None


class EvaluationService:
    """
    Evaluation service for weather forecasting models.
    
    Calculates accuracy metrics and ranks models.
    """
    
    def __init__(self):
        """Initialize EvaluationService."""
        self.metrics_history = []
    
    def calculate_mae(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Calculate Mean Absolute Error.
        
        Args:
            y_true: Actual values
            y_pred: Predicted values
        
        Returns:
            MAE value
        
        Requirements:
            - Validates Requirements 6.2
        """
        return np.mean(np.abs(y_true - y_pred))
    
    def calculate_rmse(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Calculate Root Mean Square Error.
        
        Args:
            y_true: Actual values
            y_pred: Predicted values
        
        Returns:
            RMSE value
        
        Requirements:
            - Validates Requirements 6.3
        """
        return np.sqrt(np.mean((y_true - y_pred) ** 2))
    
    def calculate_mape(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Calculate Mean Absolute Percentage Error.
        
        Args:
            y_true: Actual values
            y_pred: Predicted values
        
        Returns:
            MAPE value (percentage)
        
        Requirements:
            - Validates Requirements 6.4
        """
        return np.mean(np.abs((y_true - y_pred) / (y_true + 1e-10))) * 100
    
    def evaluate_prediction(self, model_id: str, weather_param: str,
                          y_true: np.ndarray, y_pred: np.ndarray,
                          forecast_horizon: int,
                          country: Optional[str] = None,
                          location: Optional[str] = None) -> EvaluationMetric:
        """
        Evaluate a model prediction.
        
        Args:
            model_id: Model identifier
            weather_param: Weather parameter name
            y_true: Actual values
            y_pred: Predicted values
            forecast_horizon: Forecast horizon in hours
            country: Country name (optional)
            location: Location name (optional)
        
        Returns:
            EvaluationMetric object
        
        Requirements:
            - Validates Requirements 6.1, 6.5
        """
        mae = self.calculate_mae(y_true, y_pred)
        rmse = self.calculate_rmse(y_true, y_pred)
        mape = self.calculate_mape(y_true, y_pred)
        
        metric = EvaluationMetric(
            model_id=model_id,
            weather_parameter=weather_param,
            forecast_horizon=forecast_horizon,
            mae=mae,
            rmse=rmse,
            mape=mape,
            evaluated_at=datetime.now(),
            country=country,
            location=location
        )
        
        self.metrics_history.append(metric)
        logger.info(f"Evaluated {model_id} for {weather_param}: MAE={mae:.4f}, RMSE={rmse:.4f}, MAPE={mape:.2f}%")
        
        return metric
    
    def rank_models(self, weather_param: str,
                   metric_type: str = 'mae') -> List[Dict]:
        """
        Rank models by performance metric.
        
        Args:
            weather_param: Weather parameter to rank models for
            metric_type: Metric to use for ranking ('mae', 'rmse', 'mape')
        
        Returns:
            List of model rankings
        
        Requirements:
            - Validates Requirements 7.1, 7.2, 7.3, 7.5
        """
        # Filter metrics for this parameter
        param_metrics = [m for m in self.metrics_history if m.weather_parameter == weather_param]
        
        if not param_metrics:
            return []
        
        # Group by model_id and calculate average metric
        model_scores = {}
        for metric in param_metrics:
            if metric.model_id not in model_scores:
                model_scores[metric.model_id] = []
            
            if metric_type == 'mae':
                model_scores[metric.model_id].append(metric.mae)
            elif metric_type == 'rmse':
                model_scores[metric.model_id].append(metric.rmse)
            elif metric_type == 'mape':
                model_scores[metric.model_id].append(metric.mape)
        
        # Calculate averages and rank
        rankings = []
        for model_id, scores in model_scores.items():
            avg_score = np.mean(scores)
            rankings.append({
                'model_id': model_id,
                'weather_parameter': weather_param,
                'metric_type': metric_type,
                'average_score': avg_score,
                'num_evaluations': len(scores)
            })
        
        # Sort by score (lower is better)
        rankings.sort(key=lambda x: x['average_score'])
        
        return rankings
    
    def get_model_comparison(self, weather_param: str,
                           window_days: int = 30) -> Dict:
        """
        Generate model comparison report.
        
        Args:
            weather_param: Weather parameter
            window_days: Rolling window in days
        
        Returns:
            Comparison report dictionary
        
        Requirements:
            - Validates Requirements 7.1, 7.2, 7.3, 7.5
        """
        cutoff_date = datetime.now() - timedelta(days=window_days)
        
        # Filter recent metrics
        recent_metrics = [
            m for m in self.metrics_history
            if m.weather_parameter == weather_param and m.evaluated_at >= cutoff_date
        ]
        
        if not recent_metrics:
            return {'error': 'No recent metrics found'}
        
        # Group by model
        model_stats = {}
        for metric in recent_metrics:
            if metric.model_id not in model_stats:
                model_stats[metric.model_id] = {
                    'mae_values': [],
                    'rmse_values': [],
                    'mape_values': []
                }
            
            model_stats[metric.model_id]['mae_values'].append(metric.mae)
            model_stats[metric.model_id]['rmse_values'].append(metric.rmse)
            model_stats[metric.model_id]['mape_values'].append(metric.mape)
        
        # Calculate statistics
        comparison = {
            'weather_parameter': weather_param,
            'window_days': window_days,
            'models': {}
        }
        
        for model_id, stats in model_stats.items():
            comparison['models'][model_id] = {
                'mae_mean': np.mean(stats['mae_values']),
                'mae_std': np.std(stats['mae_values']),
                'rmse_mean': np.mean(stats['rmse_values']),
                'rmse_std': np.std(stats['rmse_values']),
                'mape_mean': np.mean(stats['mape_values']),
                'mape_std': np.std(stats['mape_values']),
                'num_evaluations': len(stats['mae_values'])
            }
        
        return comparison
    
    def flag_recommended_model(self, weather_param: str,
                              consecutive_days: int = 30) -> Optional[str]:
        """
        Flag model as recommended if it has lowest MAE for consecutive days.
        
        Args:
            weather_param: Weather parameter
            consecutive_days: Number of consecutive days required
        
        Returns:
            Model ID if one should be recommended, None otherwise
        
        Requirements:
            - Validates Requirements 7.4
        """
        cutoff_date = datetime.now() - timedelta(days=consecutive_days)
        
        # Get recent metrics
        recent_metrics = [
            m for m in self.metrics_history
            if m.weather_parameter == weather_param and m.evaluated_at >= cutoff_date
        ]
        
        if not recent_metrics:
            return None
        
        # Group by date and find best model each day
        daily_best = {}
        for metric in recent_metrics:
            date_key = metric.evaluated_at.date()
            if date_key not in daily_best:
                daily_best[date_key] = metric
            elif metric.mae < daily_best[date_key].mae:
                daily_best[date_key] = metric
        
        # Check if same model was best for all days
        if len(daily_best) < consecutive_days:
            return None
        
        best_models = [m.model_id for m in daily_best.values()]
        if len(set(best_models)) == 1:
            return best_models[0]
        
        return None
