"""Unit tests for the NLP intent engine.

Verifies correct classification mapping and slot extraction from user queries.
"""

import pytest
from nlp_engine import NLPEngine


class TestNLPEngine:
    """Tests the parsing capability of NLPEngine using rules and regex."""

    @pytest.fixture
    def engine(self):
        """Pre-initializes the NLP classifier."""
        return NLPEngine(spacy_model="en_core_web_sm")

    def test_classify_greet_intent(self, engine):
        """Verifies hello greetings map correctly."""
        res = engine.parse("Hello Nova")
        assert res["intent"] == "greet"

    def test_classify_weather_intent_and_extract_city(self, engine):
        """Ensures weather requests classify and grab target city."""
        res = engine.parse("What is the weather in Hyderabad?")
        assert res["intent"] == "weather"
        assert res["entities"].get("city") == "Hyderabad"

    def test_classify_email_intent(self, engine):
        """Verifies email requests parse sender and subject."""
        res = engine.parse("Send an email to Rahul with subject project report")
        assert res["intent"] == "send_email"
        assert res["entities"].get("recipient_name") == "Rahul"
        assert res["entities"].get("subject") == "project report"

    def test_classify_reminder_intent(self, engine):
        """Verifies reminders extract temporal parameters and note details."""
        res = engine.parse("remind me to wake up in 10 minutes")
        assert res["intent"] == "set_reminder"
        assert res["entities"].get("reminder_note") == "wake up"
        assert res["entities"].get("time_expression") == "in 10 minutes"

    def test_classify_smart_home_intent(self, engine):
        """Verifies smart home triggers toggle lights or change thermostat."""
        res = engine.parse("turn off the bedroom lights")
        assert res["intent"] == "smart_home"
        assert res["entities"].get("device_action") == "turn_off"
        assert res["entities"].get("device_type") == "light"

    def test_classify_knowledge_intent(self, engine):
        """Ensures facts lookups parse topic queries."""
        res = engine.parse("tell me about Rayleigh scattering")
        assert res["intent"] == "general_knowledge"
        assert res["entities"].get("query") == "Rayleigh scattering"

    def test_classify_unknown_intent(self, engine):
        """Tests that random utterances fall back to unknown."""
        res = engine.parse("supercalifragilisticexpialidocious")
        assert res["intent"] == "unknown"
