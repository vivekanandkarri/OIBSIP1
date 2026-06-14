"""Reminder handler module for PyVoice Assistant.

Uses APScheduler to schedule background jobs. Parses relative ("in 10 minutes")
and absolute ("at 6 PM") voice commands and triggers spoken reminders.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from handlers.base_handler import BaseHandler, HandlerError

logger = logging.getLogger("PyVoice.Handlers.Reminder")


class ReminderHandler(BaseHandler):
    """Manages scheduling of user-requested reminders with voice notifications."""

    def __init__(self, config: Dict[str, Any]):
        """Initializes the reminder handler and starts the scheduler."""
        super().__init__(config)
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("APScheduler background scheduler started.")

    def execute(self, 
                entities: Dict[str, Any], 
                speak_fn: Optional[Callable[[str], None]] = None) -> str:
        """Schedules a new reminder based on time expression and note.

        Args:
            entities: Extracted entities, should contain "time_expression" and "reminder_note".
            speak_fn: Speech callback to alert the user when the reminder triggers.

        Returns:
            Confirmation statement of the scheduled reminder.
        """
        note = entities.get("reminder_note", "Timer finished")
        time_expr = entities.get("time_expression")

        if not time_expr:
            raise HandlerError("I couldn't understand when you wanted the reminder scheduled.")

        # Parse target datetime
        target_dt = self._parse_time(time_expr)
        if not target_dt:
            raise HandlerError(f"I couldn't parse the time '{time_expr}'. Please try again.")

        if target_dt <= datetime.now():
            raise HandlerError("The calculated time for the reminder is in the past.")

        # Job function to run when reminder fires
        def trigger_job():
            msg = f"Reminder alert: {note}"
            logger.info(f"Triggering reminder: '{note}'")
            if speak_fn:
                speak_fn(msg)
            else:
                print(f"\n[ALERT] {msg}\n")

        # Schedule the job
        job_id = f"reminder_{int(target_dt.timestamp())}"
        self.scheduler.add_job(
            trigger_job,
            'date',
            run_date=target_dt,
            id=job_id
        )

        formatted_time = target_dt.strftime("%I:%M %p")
        logger.info(f"Scheduled reminder '{note}' for {target_dt}")
        
        # Friendly response description
        if "in" in time_expr:
            return f"I have set a reminder to {note} {time_expr}."
        return f"I have set a reminder to {note} at {formatted_time}."

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """Parses speech time expressions into concrete datetimes.

        Supports:
        - Relative: 'in 5 minutes', 'in 2 hours', 'in 30 seconds'
        - Absolute: 'at 6:30 pm', 'at 8 am', 'at 18:00'
        """
        now = datetime.now()
        time_clean = time_str.lower().strip()

        # Case 1: Relative "in X minutes/hours/seconds"
        relative_match = re.search(r"in\s+(\d+)\s+(minute|minutes|hour|hours|second|seconds|day|days)", time_clean)
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2)
            
            if "minute" in unit:
                return now + timedelta(minutes=amount)
            elif "hour" in unit:
                return now + timedelta(hours=amount)
            elif "second" in unit:
                return now + timedelta(seconds=amount)
            elif "day" in unit:
                return now + timedelta(days=amount)

        # Case 2: Absolute "at H:M AM/PM" or "at H AM/PM" or "at H:M"
        # Match time components
        abs_match = re.search(r"(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_clean)
        if abs_match:
            hour = int(abs_match.group(1))
            minute = int(abs_match.group(2)) if abs_match.group(2) else 0
            meridian = abs_match.group(3)

            # Adjust for AM/PM
            if meridian:
                if meridian == "pm" and hour < 12:
                    hour += 12
                elif meridian == "am" and hour == 12:
                    hour = 0
            
            # Construct candidate datetime today
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If candidate is in the past (e.g. asking for "at 8" at 10 AM, we assume tomorrow 8 AM or next occurrence)
            if candidate <= now:
                # If no meridian specified and it's less than 12 hours away in a 12-hour format, add 12 hours
                if not meridian and hour <= 12 and (candidate + timedelta(hours=12)) > now:
                    candidate += timedelta(hours=12)
                else:
                    candidate += timedelta(days=1)
            
            return candidate

        return None

    def shutdown(self):
        """Cleanly stops the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped.")
        
    def __del__(self):
        """Ensures scheduler is stopped when handler is destroyed."""
        try:
            self.shutdown()
        except Exception:
            pass
