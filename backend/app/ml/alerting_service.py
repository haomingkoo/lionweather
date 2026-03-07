"""
Alerting Service for ML Weather Forecasting

Monitors model performance, prediction drift, and data quality.
Sends notifications when thresholds are exceeded.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import sqlite3
import os

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DATABASE_PATH", "weather.db")


@dataclass
class Alert:
    """Alert data structure"""
    alert_type: str  # 'accuracy', 'drift', 'data_quality'
    severity: str  # 'warning', 'critical'
    message: str
    details: Dict[str, Any]
    created_at: datetime
    model_id: Optional[str] = None
    weather_parameter: Optional[str] = None


@dataclass
class AlertConfig:
    """Alert configuration"""
    mae_threshold: float = 5.0  # Trigger alert if MAE exceeds this
    rmse_threshold: float = 7.0
    mape_threshold: float = 20.0  # Percentage
    drift_threshold: float = 0.3  # KS test p-value threshold
    missing_data_threshold: float = 0.1  # 10% missing data
    outlier_threshold: float = 0.05  # 5% outliers
    alert_cooldown_hours: int = 24  # Don't send same alert within this period
    enabled_alerts: List[str] = None  # List of enabled alert types
    
    def __post_init__(self):
        if self.enabled_alerts is None:
            self.enabled_alerts = ['accuracy', 'drift', 'data_quality']


class AlertingService:
    """
    Alerting service for monitoring ML weather forecasting system.
    
    Monitors:
    - Model accuracy metrics (MAE, RMSE, MAPE)
    - Prediction drift (distribution shifts)
    - Data quality (missing data, outliers, API failures)
    """
    
    def __init__(self, config: Optional[AlertConfig] = None):
        """
        Initialize AlertingService.
        
        Args:
            config: Alert configuration (uses defaults if None)
        """
        self.config = config or AlertConfig()
        self.alert_history: List[Alert] = []
        self._init_alert_table()
    async def send_notification(self, alert: Alert, channels: List[str] = None):
        """
        Send alert notification through configured channels.

        Args:
            alert: Alert to send
            channels: List of channels ('email', 'slack', 'discord').
                     If None, uses all configured channels.

        Requirements:
            - Implements Task 21.2: Notification delivery
        """
        if channels is None:
            channels = ['email', 'slack', 'discord']

        results = {}

        if 'email' in channels:
            results['email'] = await self._send_email_notification(alert)

        if 'slack' in channels:
            results['slack'] = await self._send_slack_notification(alert)

        if 'discord' in channels:
            results['discord'] = await self._send_discord_notification(alert)

        return results

    async def _send_email_notification(self, alert: Alert) -> Dict[str, Any]:
        """
        Send email notification via SMTP.

        Environment variables required:
            - SMTP_HOST: SMTP server hostname (e.g., smtp.gmail.com)
            - SMTP_PORT: SMTP server port (e.g., 587 for TLS)
            - SMTP_USER: SMTP username/email
            - SMTP_PASSWORD: SMTP password or app-specific password
            - ALERT_EMAIL_TO: Recipient email address

        Returns:
            Dict with success status and message
        """
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_host = os.getenv('SMTP_HOST')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_user = os.getenv('SMTP_USER')
        smtp_password = os.getenv('SMTP_PASSWORD')
        recipient = os.getenv('ALERT_EMAIL_TO')

        if not all([smtp_host, smtp_user, smtp_password, recipient]):
            logger.warning("Email notification skipped: SMTP credentials not configured")
            return {'success': False, 'reason': 'not_configured'}

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert.severity.upper()}] Weather ML Alert: {alert.alert_type}"
            msg['From'] = smtp_user
            msg['To'] = recipient

            # Generate email body
            text_body = self._generate_email_text(alert)
            html_body = self._generate_email_html(alert)

            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            # Send email
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

            logger.info(f"Email notification sent for alert: {alert.alert_type}")
            return {'success': True, 'recipient': recipient}

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return {'success': False, 'error': str(e)}

    async def _send_slack_notification(self, alert: Alert) -> Dict[str, Any]:
        """
        Send Slack notification via webhook.

        Environment variables required:
            - SLACK_WEBHOOK_URL: Slack incoming webhook URL

        Returns:
            Dict with success status and message
        """
        import aiohttp

        webhook_url = os.getenv('SLACK_WEBHOOK_URL')

        if not webhook_url:
            logger.warning("Slack notification skipped: webhook URL not configured")
            return {'success': False, 'reason': 'not_configured'}

        try:
            # Generate Slack message
            payload = self._generate_slack_payload(alert)

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Slack notification sent for alert: {alert.alert_type}")
                        return {'success': True}
                    else:
                        error_text = await response.text()
                        logger.error(f"Slack webhook failed: {response.status} - {error_text}")
                        return {'success': False, 'error': error_text}

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return {'success': False, 'error': str(e)}

    async def _send_discord_notification(self, alert: Alert) -> Dict[str, Any]:
        """
        Send Discord notification via webhook.

        Environment variables required:
            - DISCORD_WEBHOOK_URL: Discord webhook URL

        Returns:
            Dict with success status and message
        """
        import aiohttp

        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

        if not webhook_url:
            logger.warning("Discord notification skipped: webhook URL not configured")
            return {'success': False, 'reason': 'not_configured'}

        try:
            # Generate Discord message
            payload = self._generate_discord_payload(alert)

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status in (200, 204):
                        logger.info(f"Discord notification sent for alert: {alert.alert_type}")
                        return {'success': True}
                    else:
                        error_text = await response.text()
                        logger.error(f"Discord webhook failed: {response.status} - {error_text}")
                        return {'success': False, 'error': error_text}

        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return {'success': False, 'error': str(e)}
    def _generate_email_text(self, alert: Alert) -> str:
        """Generate plain text email body"""
        lines = [
            f"Weather ML Alert - {alert.severity.upper()}",
            f"Type: {alert.alert_type}",
            f"Time: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"Message: {alert.message}",
            "",
            "Details:",
        ]

        for key, value in alert.details.items():
            lines.append(f"  {key}: {value}")

        lines.extend([
            "",
            "---",
            "This is an automated alert from the Weather ML Forecasting System.",
            "To configure alert settings, visit the dashboard."
        ])

        return "\n".join(lines)

    def _generate_email_html(self, alert: Alert) -> str:
        """Generate HTML email body"""
        severity_color = '#dc2626' if alert.severity == 'critical' else '#f59e0b'

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: {severity_color}; color: white; padding: 20px; }}
                .content {{ padding: 20px; }}
                .details {{ background-color: #f3f4f6; padding: 15px; border-radius: 5px; }}
                .detail-item {{ margin: 5px 0; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>Weather ML Alert - {alert.severity.upper()}</h2>
            </div>
            <div class="content">
                <p><strong>Type:</strong> {alert.alert_type}</p>
                <p><strong>Time:</strong> {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Message:</strong> {alert.message}</p>

                <div class="details">
                    <h3>Details</h3>
        """

        for key, value in alert.details.items():
            html += f'<div class="detail-item"><strong>{key}:</strong> {value}</div>\n'

        html += """
                </div>

                <div class="footer">
                    This is an automated alert from the Weather ML Forecasting System.<br>
                    To configure alert settings, visit the dashboard.
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _generate_slack_payload(self, alert: Alert) -> Dict[str, Any]:
        """Generate Slack message payload"""
        severity_emoji = '🔴' if alert.severity == 'critical' else '⚠️'
        severity_color = 'danger' if alert.severity == 'critical' else 'warning'

        # Format details as fields
        fields = []
        for key, value in alert.details.items():
            fields.append({
                'title': key.replace('_', ' ').title(),
                'value': str(value),
                'short': len(str(value)) < 40
            })

        return {
            'text': f"{severity_emoji} Weather ML Alert",
            'attachments': [{
                'color': severity_color,
                'title': f"{alert.alert_type.upper()} Alert",
                'text': alert.message,
                'fields': fields,
                'footer': 'Weather ML Forecasting System',
                'ts': int(alert.created_at.timestamp())
            }]
        }

    def _generate_discord_payload(self, alert: Alert) -> Dict[str, Any]:
        """Generate Discord message payload"""
        severity_emoji = '🔴' if alert.severity == 'critical' else '⚠️'
        severity_color = 0xdc2626 if alert.severity == 'critical' else 0xf59e0b

        # Format details as fields
        fields = []
        for key, value in alert.details.items():
            fields.append({
                'name': key.replace('_', ' ').title(),
                'value': str(value),
                'inline': len(str(value)) < 40
            })

        return {
            'embeds': [{
                'title': f"{severity_emoji} {alert.alert_type.upper()} Alert",
                'description': alert.message,
                'color': severity_color,
                'fields': fields,
                'footer': {
                    'text': 'Weather ML Forecasting System'
                },
                'timestamp': alert.created_at.isoformat()
            }]
        }
    
    def _init_alert_table(self):
        """Create alerts table if it doesn't exist"""
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT NOT NULL,
                model_id TEXT,
                weather_parameter TEXT,
                created_at TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0,
                acknowledged_at TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_created 
            ON alerts(created_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_type 
            ON alerts(alert_type, created_at)
        """)
        
        con.commit()
        con.close()
    
    def check_model_accuracy(self, model_id: str, weather_parameter: str,
                           window_hours: int = 24) -> Optional[Alert]:
        """
        Check if model accuracy metrics exceed thresholds.
        
        Args:
            model_id: Model identifier
            weather_parameter: Weather parameter name
            window_hours: Time window to check (hours)
        
        Returns:
            Alert if threshold exceeded, None otherwise
        
        Requirements:
            - Implements Task 21.1: Monitor MAE thresholds
        """
        if 'accuracy' not in self.config.enabled_alerts:
            return None
        
        # Check if we recently sent this alert (cooldown)
        if self._is_in_cooldown('accuracy', model_id, weather_parameter):
            return None
        
        # Get recent evaluation metrics
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        
        cutoff_time = (datetime.now() - timedelta(hours=window_hours)).isoformat()
        
        cursor.execute("""
            SELECT 
                AVG(absolute_error) as avg_mae,
                AVG(squared_error) as avg_mse,
                AVG(percentage_error) as avg_mape,
                COUNT(*) as count
            FROM evaluation_metrics
            WHERE model_id = ? 
                AND weather_parameter = ?
                AND evaluation_timestamp >= ?
        """, (model_id, weather_parameter, cutoff_time))
        
        result = cursor.fetchone()
        con.close()
        
        if not result or result[3] == 0:  # No data
            return None
        
        avg_mae, avg_mse, avg_mape, count = result
        avg_rmse = np.sqrt(avg_mse) if avg_mse else 0
        
        # Check thresholds
        alert = None
        if avg_mae > self.config.mae_threshold:
            alert = Alert(
                alert_type='accuracy',
                severity='critical' if avg_mae > self.config.mae_threshold * 1.5 else 'warning',
                message=f'Model accuracy degraded: MAE {avg_mae:.2f} exceeds threshold {self.config.mae_threshold}',
                details={
                    'model_id': model_id,
                    'weather_parameter': weather_parameter,
                    'mae': avg_mae,
                    'rmse': avg_rmse,
                    'mape': avg_mape,
                    'threshold': self.config.mae_threshold,
                    'window_hours': window_hours,
                    'sample_count': count
                },
                created_at=datetime.now(),
                model_id=model_id,
                weather_parameter=weather_parameter
            )
        elif avg_rmse > self.config.rmse_threshold:
            alert = Alert(
                alert_type='accuracy',
                severity='warning',
                message=f'Model RMSE {avg_rmse:.2f} exceeds threshold {self.config.rmse_threshold}',
                details={
                    'model_id': model_id,
                    'weather_parameter': weather_parameter,
                    'mae': avg_mae,
                    'rmse': avg_rmse,
                    'mape': avg_mape,
                    'threshold': self.config.rmse_threshold,
                    'window_hours': window_hours,
                    'sample_count': count
                },
                created_at=datetime.now(),
                model_id=model_id,
                weather_parameter=weather_parameter
            )
        elif avg_mape > self.config.mape_threshold:
            alert = Alert(
                alert_type='accuracy',
                severity='warning',
                message=f'Model MAPE {avg_mape:.2f}% exceeds threshold {self.config.mape_threshold}%',
                details={
                    'model_id': model_id,
                    'weather_parameter': weather_parameter,
                    'mae': avg_mae,
                    'rmse': avg_rmse,
                    'mape': avg_mape,
                    'threshold': self.config.mape_threshold,
                    'window_hours': window_hours,
                    'sample_count': count
                },
                created_at=datetime.now(),
                model_id=model_id,
                weather_parameter=weather_parameter
            )
        
        if alert:
            self._save_alert(alert)
            logger.warning(f"Accuracy alert: {alert.message}")
        
        return alert
    
    def check_prediction_drift(self, model_id: str, weather_parameter: str,
                              recent_window_hours: int = 24,
                              baseline_window_hours: int = 168) -> Optional[Alert]:
        """
        Detect prediction drift by comparing recent predictions to historical baseline.
        
        Uses Kolmogorov-Smirnov test to detect distribution shifts.
        
        Args:
            model_id: Model identifier
            weather_parameter: Weather parameter name
            recent_window_hours: Recent time window (default 24 hours)
            baseline_window_hours: Baseline time window (default 7 days)
        
        Returns:
            Alert if drift detected, None otherwise
        
        Requirements:
            - Implements Task 21.1: Detect distribution shifts
        """
        if 'drift' not in self.config.enabled_alerts:
            return None
        
        # Check cooldown
        if self._is_in_cooldown('drift', model_id, weather_parameter):
            return None
        
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        
        # Get recent predictions
        recent_cutoff = (datetime.now() - timedelta(hours=recent_window_hours)).isoformat()
        cursor.execute("""
            SELECT predicted_value
            FROM predictions
            WHERE model_id = ? 
                AND weather_parameter = ?
                AND prediction_timestamp >= ?
        """, (model_id, weather_parameter, recent_cutoff))
        
        recent_predictions = [row[0] for row in cursor.fetchall()]
        
        # Get baseline predictions
        baseline_start = (datetime.now() - timedelta(hours=baseline_window_hours)).isoformat()
        baseline_end = recent_cutoff
        cursor.execute("""
            SELECT predicted_value
            FROM predictions
            WHERE model_id = ? 
                AND weather_parameter = ?
                AND prediction_timestamp >= ?
                AND prediction_timestamp < ?
        """, (model_id, weather_parameter, baseline_start, baseline_end))
        
        baseline_predictions = [row[0] for row in cursor.fetchall()]
        con.close()
        
        # Need sufficient data for statistical test
        if len(recent_predictions) < 10 or len(baseline_predictions) < 30:
            return None
        
        # Perform Kolmogorov-Smirnov test
        ks_statistic, p_value = stats.ks_2samp(recent_predictions, baseline_predictions)
        
        # Low p-value indicates distributions are different (drift detected)
        if p_value < self.config.drift_threshold:
            recent_mean = np.mean(recent_predictions)
            baseline_mean = np.mean(baseline_predictions)
            mean_shift = recent_mean - baseline_mean
            
            alert = Alert(
                alert_type='drift',
                severity='critical' if p_value < 0.01 else 'warning',
                message=f'Prediction drift detected: distribution shift in {weather_parameter} predictions',
                details={
                    'model_id': model_id,
                    'weather_parameter': weather_parameter,
                    'ks_statistic': ks_statistic,
                    'p_value': p_value,
                    'recent_mean': recent_mean,
                    'baseline_mean': baseline_mean,
                    'mean_shift': mean_shift,
                    'recent_samples': len(recent_predictions),
                    'baseline_samples': len(baseline_predictions)
                },
                created_at=datetime.now(),
                model_id=model_id,
                weather_parameter=weather_parameter
            )
            
            self._save_alert(alert)
            logger.warning(f"Drift alert: {alert.message}")
            return alert
        
        return None
    
    def check_data_quality(self, country: str, window_hours: int = 24) -> Optional[Alert]:
        """
        Monitor data quality issues: missing data, outliers, API failures.
        
        Args:
            country: Country to check
            window_hours: Time window to check (hours)
        
        Returns:
            Alert if data quality issues detected, None otherwise
        
        Requirements:
            - Implements Task 21.1: Monitor missing/invalid data
        """
        if 'data_quality' not in self.config.enabled_alerts:
            return None
        
        # Check cooldown
        if self._is_in_cooldown('data_quality', country, None):
            return None
        
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        
        cutoff_time = (datetime.now() - timedelta(hours=window_hours)).isoformat()
        
        # Count expected vs actual records
        # Assuming hourly data collection, we expect ~window_hours records per location
        cursor.execute("""
            SELECT 
                location,
                COUNT(*) as record_count
            FROM weather_records
            WHERE country = ?
                AND timestamp >= ?
            GROUP BY location
        """, (country, cutoff_time))
        
        location_counts = cursor.fetchall()
        
        # Get all locations for this country
        cursor.execute("""
            SELECT DISTINCT location
            FROM weather_records
            WHERE country = ?
        """, (country,))
        
        all_locations = [row[0] for row in cursor.fetchall()]
        
        # Check for missing data
        missing_locations = []
        low_data_locations = []
        
        location_count_dict = {loc: count for loc, count in location_counts}
        
        for location in all_locations:
            count = location_count_dict.get(location, 0)
            expected_count = window_hours  # Hourly data
            
            if count == 0:
                missing_locations.append(location)
            elif count < expected_count * (1 - self.config.missing_data_threshold):
                low_data_locations.append((location, count, expected_count))
        
        # Check for outliers
        cursor.execute("""
            SELECT 
                temperature,
                rainfall,
                humidity,
                wind_speed
            FROM weather_records
            WHERE country = ?
                AND timestamp >= ?
        """, (country, cutoff_time))
        
        records = cursor.fetchall()
        con.close()
        
        if not records:
            return None
        
        # Calculate outlier percentage
        outlier_count = 0
        total_values = 0
        
        for temp, rain, humid, wind in records:
            values = [temp, rain, humid, wind]
            for val in values:
                if val is not None:
                    total_values += 1
                    # Check for extreme outliers (beyond reasonable ranges)
                    if (temp and (temp < -50 or temp > 60)) or \
                       (rain and rain < 0) or \
                       (humid and (humid < 0 or humid > 100)) or \
                       (wind and wind < 0):
                        outlier_count += 1
        
        outlier_rate = outlier_count / total_values if total_values > 0 else 0
        
        # Generate alert if issues detected
        issues = []
        if missing_locations:
            issues.append(f"{len(missing_locations)} locations with no data")
        if low_data_locations:
            issues.append(f"{len(low_data_locations)} locations with insufficient data")
        if outlier_rate > self.config.outlier_threshold:
            issues.append(f"{outlier_rate*100:.1f}% outlier rate")
        
        if issues:
            alert = Alert(
                alert_type='data_quality',
                severity='critical' if missing_locations else 'warning',
                message=f'Data quality issues detected for {country}: {", ".join(issues)}',
                details={
                    'country': country,
                    'window_hours': window_hours,
                    'missing_locations': missing_locations,
                    'low_data_locations': [(loc, count, exp) for loc, count, exp in low_data_locations],
                    'outlier_rate': outlier_rate,
                    'outlier_threshold': self.config.outlier_threshold,
                    'total_records': len(records)
                },
                created_at=datetime.now()
            )
            
            self._save_alert(alert)
            logger.warning(f"Data quality alert: {alert.message}")
            return alert
        
        return None
    
    def _is_in_cooldown(self, alert_type: str, identifier: str, 
                       weather_parameter: Optional[str]) -> bool:
        """
        Check if alert is in cooldown period to avoid spam.
        
        Args:
            alert_type: Type of alert
            identifier: Model ID or country
            weather_parameter: Weather parameter (optional)
        
        Returns:
            True if in cooldown, False otherwise
        """
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        
        cooldown_time = (datetime.now() - timedelta(hours=self.config.alert_cooldown_hours)).isoformat()
        
        if weather_parameter:
            cursor.execute("""
                SELECT COUNT(*)
                FROM alerts
                WHERE alert_type = ?
                    AND (model_id = ? OR details LIKE ?)
                    AND weather_parameter = ?
                    AND created_at >= ?
            """, (alert_type, identifier, f'%{identifier}%', weather_parameter, cooldown_time))
        else:
            cursor.execute("""
                SELECT COUNT(*)
                FROM alerts
                WHERE alert_type = ?
                    AND (model_id = ? OR details LIKE ?)
                    AND created_at >= ?
            """, (alert_type, identifier, f'%{identifier}%', cooldown_time))
        
        count = cursor.fetchone()[0]
        con.close()
        
        return count > 0
    
    def _save_alert(self, alert: Alert):
        """Save alert to database"""
        import json
        
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        
        cursor.execute("""
            INSERT INTO alerts (
                alert_type, severity, message, details,
                model_id, weather_parameter, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            alert.alert_type,
            alert.severity,
            alert.message,
            json.dumps(alert.details),
            alert.model_id,
            alert.weather_parameter,
            alert.created_at.isoformat()
        ))
        
        con.commit()
        con.close()
        
        self.alert_history.append(alert)
    
    def get_recent_alerts(self, hours: int = 24, 
                         alert_type: Optional[str] = None) -> List[Alert]:
        """
        Get recent alerts.
        
        Args:
            hours: Time window (hours)
            alert_type: Filter by alert type (optional)
        
        Returns:
            List of alerts
        """
        import json
        
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        if alert_type:
            cursor.execute("""
                SELECT alert_type, severity, message, details, 
                       model_id, weather_parameter, created_at
                FROM alerts
                WHERE created_at >= ?
                    AND alert_type = ?
                ORDER BY created_at DESC
            """, (cutoff_time, alert_type))
        else:
            cursor.execute("""
                SELECT alert_type, severity, message, details,
                       model_id, weather_parameter, created_at
                FROM alerts
                WHERE created_at >= ?
                ORDER BY created_at DESC
            """, (cutoff_time,))
        
        alerts = []
        for row in cursor.fetchall():
            alerts.append(Alert(
                alert_type=row[0],
                severity=row[1],
                message=row[2],
                details=json.loads(row[3]),
                model_id=row[4],
                weather_parameter=row[5],
                created_at=datetime.fromisoformat(row[6])
            ))
        
        con.close()
        return alerts
    
    def acknowledge_alert(self, alert_id: int):
        """Mark alert as acknowledged"""
        con = sqlite3.connect(DB_PATH)
        cursor = con.cursor()
        
        cursor.execute("""
            UPDATE alerts
            SET acknowledged = 1,
                acknowledged_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), alert_id))
        
        con.commit()
        con.close()
