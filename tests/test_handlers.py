"""Unit tests for PyVoice Task Handlers.

Verifies mock operations, HTTP response mocks, and error conditions.
"""

import pytest
from unittest.mock import MagicMock, patch
from handlers.weather_handler import WeatherHandler
from handlers.email_handler import EmailHandler
from handlers.reminder_handler import ReminderHandler
from handlers.smart_home_handler import SmartHomeHandler
from handlers.knowledge_handler import KnowledgeHandler
from handlers.base_handler import HandlerError


class TestWeatherHandler:
    """Verifies OpenWeatherMap fetching and forecast formatting."""

    def test_weather_mock_fallback(self):
        """Tests that weather handler returns a mock report if API key is not present."""
        config = {"user": {"default_city": "Delhi"}}
        handler = WeatherHandler(config)
        
        # Executes without key
        resp = handler.execute({"city": "Delhi"})
        assert "Delhi" in resp
        assert "3-day forecast" in resp


class TestEmailHandler:
    """Checks SMTP setups, body parsing, and voice confirmations."""

    def test_email_cancellation(self):
        """Ensures email is not sent if user rejects confirmation."""
        config = {}
        handler = EmailHandler(config)

        speak_mock = MagicMock()
        listen_mock = MagicMock(return_value="no")

        entities = {
            "recipient_name": "Rahul",
            "subject": "Test",
            "body": "Hello"
        }

        resp = handler.execute(entities, speak_fn=speak_mock, listen_fn=listen_mock)
        assert resp == "Email sending cancelled."
        speak_mock.assert_any_call("I have drafted an email for Rahul with subject 'Test'. Should I send it?")


class TestReminderHandler:
    """Checks APScheduler timers and voice alarms."""

    def test_relative_time_parsing(self):
        """Verifies that time parsing handles relative minutes correctly."""
        handler = ReminderHandler({})
        dt = handler._parse_time("in 15 minutes")
        
        assert dt is not None
        # Difference should be approx 15 mins (900 seconds)
        import datetime
        diff = (dt - datetime.datetime.now()).total_seconds()
        assert 890 < diff < 910
        handler.shutdown()


class TestSmartHomeHandler:
    """Tests Home Assistant API triggers and local states."""

    def test_mock_device_state_toggles(self):
        """Ensures mock devices toggle state inside local state dictionary."""
        handler = SmartHomeHandler({})
        
        # Turn bedroom lights on
        resp = handler.execute({
            "device_type": "light",
            "device_action": "turn_on"
        })
        assert "lights on" in resp.lower()

        # Check status
        status_resp = handler.execute({
            "device_type": "light",
            "device_action": "status"
        })
        assert "on" in status_resp


class TestKnowledgeHandler:
    """Tests Wikipedia lookups and response truncation."""

    @patch('handlers.knowledge_handler.KnowledgeHandler._search_wikipedia')
    def test_wikipedia_truncation(self, mock_wiki):
        """Ensures long search extracts are truncated to 3 sentences."""
        mock_wiki.return_value = (
            "Sentence one. Sentence two? Sentence three! Sentence four. Sentence five."
        )
        handler = KnowledgeHandler({})
        
        resp = handler.execute({"query": "python programming"})
        
        assert "Sentence one." in resp
        assert "Sentence three!" in resp
        assert "Sentence four." not in resp
