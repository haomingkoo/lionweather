"""
Alert and Notification API Endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta

from ..ml.alerting_service import AlertingService, AlertConfig, Alert
from ..ml.notification_service import NotificationService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/recent")
async def get_recent_alerts(
    hours: int = Query(24, ge=1, le=168, description="Time window in hours"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type")
):
    """
    Get recent alerts.
    
    Args:
        hours: Time window (1-168 hours)
        alert_type: Optional filter by type ('accuracy', 'drift', 'data_quality')
    
    Returns:
        List of recent alerts
    """
    service = AlertingService()
    alerts = service.get_recent_alerts(hours=hours, alert_type=alert_type)
    
    return {
        'alerts': [
            {
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'details': alert.details,
                'model_id': alert.model_id,
                'weather_parameter': alert.weather_parameter,
                'created_at': alert.created_at.isoformat()
            }
            for alert in alerts
        ],
        'count': len(alerts),
        'time_window_hours': hours
    }


@router.post("/check/accuracy")
async def check_model_accuracy(
    model_id: str,
    weather_parameter: str,
    window_hours: int = Query(24, ge=1, le=168)
):
    """
    Manually trigger accuracy check for a model.
    
    Args:
        model_id: Model identifier
        weather_parameter: Weather parameter name
        window_hours: Time window to check
    
    Returns:
        Alert if threshold exceeded, None otherwise
    """
    service = AlertingService()
    alert = service.check_model_accuracy(
        model_id=model_id,
        weather_parameter=weather_parameter,
        window_hours=window_hours
    )
    
    if alert:
        # Send notification if configured
        notification_service = NotificationService()
        channels = notification_service.get_config().get_enabled_channels()
        if channels:
            await service.send_notification(alert, channels)
        
        return {
            'alert_triggered': True,
            'alert': {
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'details': alert.details
            }
        }
    
    return {'alert_triggered': False, 'message': 'No threshold exceeded'}


@router.post("/check/drift")
async def check_prediction_drift(
    model_id: str,
    weather_parameter: str,
    recent_window_hours: int = Query(24, ge=1, le=168),
    baseline_window_hours: int = Query(168, ge=24, le=720)
):
    """
    Manually trigger drift detection for a model.
    
    Args:
        model_id: Model identifier
        weather_parameter: Weather parameter name
        recent_window_hours: Recent time window
        baseline_window_hours: Baseline time window
    
    Returns:
        Alert if drift detected, None otherwise
    """
    service = AlertingService()
    alert = service.check_prediction_drift(
        model_id=model_id,
        weather_parameter=weather_parameter,
        recent_window_hours=recent_window_hours,
        baseline_window_hours=baseline_window_hours
    )
    
    if alert:
        # Send notification if configured
        notification_service = NotificationService()
        channels = notification_service.get_config().get_enabled_channels()
        if channels:
            await service.send_notification(alert, channels)
        
        return {
            'alert_triggered': True,
            'alert': {
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'details': alert.details
            }
        }
    
    return {'alert_triggered': False, 'message': 'No drift detected'}


@router.post("/check/data-quality")
async def check_data_quality(
    country: str,
    window_hours: int = Query(24, ge=1, le=168)
):
    """
    Manually trigger data quality check.
    
    Args:
        country: Country to check
        window_hours: Time window to check
    
    Returns:
        Alert if issues detected, None otherwise
    """
    service = AlertingService()
    alert = service.check_data_quality(
        country=country,
        window_hours=window_hours
    )
    
    if alert:
        # Send notification if configured
        notification_service = NotificationService()
        channels = notification_service.get_config().get_enabled_channels()
        if channels:
            await service.send_notification(alert, channels)
        
        return {
            'alert_triggered': True,
            'alert': {
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'details': alert.details
            }
        }
    
    return {'alert_triggered': False, 'message': 'No data quality issues detected'}


@router.get("/config")
async def get_notification_config():
    """
    Get current notification configuration.
    
    Returns:
        Notification configuration (excluding sensitive data)
    """
    service = NotificationService()
    return service.get_config().to_dict()


@router.post("/test/{channel}")
async def test_notification(channel: str):
    """
    Send a test notification to verify configuration.
    
    Args:
        channel: Channel to test ('email', 'slack', 'discord')
    
    Returns:
        Test result
    """
    if channel not in ['email', 'slack', 'discord']:
        raise HTTPException(status_code=400, detail="Invalid channel. Must be 'email', 'slack', or 'discord'")
    
    service = NotificationService()
    result = service.test_notification(channel)
    
    if result.get('success'):
        return {
            'success': True,
            'message': f'Test notification sent successfully to {channel}',
            'details': result
        }
    else:
        return {
            'success': False,
            'message': f'Failed to send test notification to {channel}',
            'details': result
        }


@router.post("/acknowledge/{alert_id}")
async def acknowledge_alert(alert_id: int):
    """
    Mark an alert as acknowledged.
    
    Args:
        alert_id: Alert ID to acknowledge
    
    Returns:
        Success message
    """
    service = AlertingService()
    service.acknowledge_alert(alert_id)
    
    return {
        'success': True,
        'message': f'Alert {alert_id} acknowledged'
    }
