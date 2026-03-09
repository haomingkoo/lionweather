"""
Automated Training Scheduler for ML Weather Forecasting

Schedules weekly model retraining check.
Actual retraining is triggered via POST /admin/retrain.
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class TrainingScheduler:
    """
    Automated training scheduler.

    Checks weekly on Sunday at 2 AM and logs a reminder.
    To trigger retraining, call POST /admin/retrain.
    """

    def __init__(self):
        """Initialize TrainingScheduler."""
        self.scheduler = AsyncIOScheduler()

    async def run_training_job(self):
        """
        Weekly training check.

        Full pipeline retraining is handled via POST /admin/retrain.
        """
        logger.info(
            "Weekly training check: use POST /admin/retrain to trigger model retraining."
        )

    def start(self):
        """Start the scheduler."""
        self.scheduler.add_job(
            self.run_training_job,
            CronTrigger(day_of_week='sun', hour=2, minute=0),
            id='weekly_training',
            name='Weekly Training Check',
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("Training scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Training scheduler stopped")
