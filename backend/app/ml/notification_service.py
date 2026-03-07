"""
Notification Service for ML Weather Forecasting

Handles notification delivery configuration and management.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import os
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class NotificationConfig:
    """Notification configuration"""
    email_enabled: bool = False
    slack_enabled: bool = False
    discord_enabled: bool = False
    
    # Email settings
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_to: Optional[str] = None
    
    # Webhook URLs
    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'NotificationConfig':
        """Load configuration from environment variables"""
        return cls(
            email_enabled=os.getenv('ALERT_EMAIL_ENABLED', 'false').lower() == 'true',
            slack_enabled=os.getenv('ALERT_SLACK_ENABLED', 'false').lower() == 'true',
            discord_enabled=os.getenv('ALERT_DISCORD_ENABLED', 'false').lower() == 'true',
            smtp_host=os.getenv('SMTP_HOST'),
            smtp_port=int(os.getenv('SMTP_PORT', '587')),
            smtp_user=os.getenv('SMTP_USER'),
            smtp_password=os.getenv('SMTP_PASSWORD'),
            email_to=os.getenv('ALERT_EMAIL_TO'),
            slack_webhook_url=os.getenv('SLACK_WEBHOOK_URL'),
            discord_webhook_url=os.getenv('DISCORD_WEBHOOK_URL')
        )
    
    def get_enabled_channels(self) -> List[str]:
        """Get list of enabled notification channels"""
        channels = []
        if self.email_enabled and self.smtp_host and self.smtp_user and self.email_to:
            channels.append('email')
        if self.slack_enabled and self.slack_webhook_url:
            channels.append('slack')
        if self.discord_enabled and self.discord_webhook_url:
            channels.append('discord')
        return channels
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive data)"""
        return {
            'email_enabled': self.email_enabled,
            'slack_enabled': self.slack_enabled,
            'discord_enabled': self.discord_enabled,
            'email_configured': bool(self.smtp_host and self.smtp_user and self.email_to),
            'slack_configured': bool(self.slack_webhook_url),
            'discord_configured': bool(self.discord_webhook_url),
            'enabled_channels': self.get_enabled_channels()
        }


class NotificationService:
    """
    Service for managing notification configuration and delivery.
    """
    
    def __init__(self):
        self.config = NotificationConfig.from_env()
    
    def get_config(self) -> NotificationConfig:
        """Get current notification configuration"""
        return self.config
    
    def reload_config(self):
        """Reload configuration from environment"""
        self.config = NotificationConfig.from_env()
    
    def test_notification(self, channel: str) -> Dict[str, Any]:
        """
        Send a test notification to verify configuration.
        
        Args:
            channel: Channel to test ('email', 'slack', 'discord')
        
        Returns:
            Dict with test result
        """
        from .alerting_service import Alert, AlertingService
        from datetime import datetime
        
        # Create test alert
        test_alert = Alert(
            alert_type='test',
            severity='warning',
            message=f'Test notification from Weather ML Forecasting System',
            details={
                'channel': channel,
                'timestamp': datetime.now().isoformat(),
                'message': 'If you receive this, your notification configuration is working correctly!'
            },
            created_at=datetime.now()
        )
        
        # Send notification
        alerting_service = AlertingService()
        
        import asyncio
        result = asyncio.run(alerting_service.send_notification(test_alert, [channel]))
        
        return result.get(channel, {'success': False, 'error': 'Unknown error'})
