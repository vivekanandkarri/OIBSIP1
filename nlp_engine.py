"""NLP Engine module for PyVoice Assistant.

Uses keyword matching, regular expressions, and optional spaCy (en_core_web_sm)
to classify user utterances into intents and extract structural entities.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("PyVoice.NLPEngine")

# Try to load spaCy, otherwise run in Regex-only mode
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("spaCy not installed. Running NLP Engine in Regex-only mode.")


class NLPEngine:
    """Classifies user speech into intents and parses parameters/entities."""

    def __init__(self, spacy_model: str = "en_core_web_sm"):
        """Initializes the NLP engine, loading spaCy model if available.

        Args:
            spacy_model: The name of the spaCy pipeline model to load.
        """
        self.nlp = None
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load(spacy_model)
                logger.info(f"Loaded spaCy model: {spacy_model}")
            except Exception as e:
                logger.warning(
                    f"Could not load spaCy model '{spacy_model}': {e}. "
                    "Falling back to Regex-only entity extraction."
                )

        # Precompiled regex patterns for intent classification
        self.intent_patterns = {
            "greet": [
                r"\b(hello|hi|hey|greetings|morning|afternoon|evening|hola|yo)\b",
                r"\bhey nova\b"
            ],
            "farewell": [
                r"\b(goodbye|bye|see you|farewell|quit|exit|stop|terminate|shutdown|go to sleep)\b"
            ],
            "weather": [
                r"\b(weather|temperature|forecast|rain|rainy|sunny|snow|windy|hot|cold|climate)\b"
            ],
            "send_email": [
                r"\b(email|mail|send a message|compose email|message to)\b"
            ],
            "set_reminder": [
                r"\b(remind|reminder|alarm|timer|alert|schedule alert)\b"
            ],
            "smart_home": [
                r"\b(light|lights|switch|plug|thermostat|ac|heating|smart home|turn on|turn off)\b"
            ],
            "general_knowledge": [
                r"\b(who|what|where|why|how|define|search|wikipedia|tell me about|info on)\b"
            ]
        }

    def parse(self, text: str) -> Dict[str, Any]:
        """Parses raw text transcription into an intent and entity dictionary.

        Args:
            text: Raw transcribed input string.

        Returns:
            A dictionary containing:
            - "raw_text": original input
            - "intent": classified intent string
            - "entities": dictionary of extracted parameters (e.g. city, recipient, datetime)
        """
        text_clean = text.strip().lower()
        
        # 1. Classify Intent
        intent = self._classify_intent(text_clean)
        
        # 2. Extract Entities
        entities = self._extract_entities(text_clean, intent)

        logger.info(f"NLP parsed input: '{text}' -> Intent: {intent}, Entities: {entities}")
        return {
            "raw_text": text,
            "intent": intent,
            "entities": entities
        }

    def _classify_intent(self, text: str) -> str:
        """Determines the intent of the input using regex patterns.

        Defaults to 'unknown' if no patterns match.
        """
        # Search patterns in order
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return intent
        return "unknown"

    def _extract_entities(self, text: str, intent: str) -> Dict[str, Any]:
        """Extracts key variables based on intent using spaCy or regular expressions."""
        entities = {}

        # 1. Extract using spaCy if available
        if self.nlp:
            try:
                doc = self.nlp(text)
                
                # Extract cities (GPE) for weather
                cities = [ent.text for ent in doc.ents if ent.label_ == "GPE"]
                if cities:
                    entities["city"] = cities[0].title()

                # Extract names (PERSON) for emails
                people = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
                if people:
                    entities["recipient_name"] = people[0].title()

                # Extract numeric values or times
                times = [ent.text for ent in doc.ents if ent.label_ in ("TIME", "DATE", "CARDINAL")]
                if times:
                    entities["time_expression"] = " ".join(times)
            except Exception as e:
                logger.error(f"spaCy entity extraction error: {e}")

        # 2. Regex-based slot filling fallbacks / refinements
        
        # Weather Specifics
        if "city" not in entities:
            # Match "in [city]" or "at [city]" or "for [city]"
            match = re.search(r"\b(?:in|at|for)\b\s+([a-zA-Z\s]+)$", text)
            if match:
                entities["city"] = match.group(1).strip().title()

        # Email Specifics
        if "recipient_name" not in entities:
            # Match "email to [recipient]" or "mail [recipient]"
            match = re.search(r"\b(?:email|mail|message|to)\b\s+([a-zA-Z]+)", text)
            if match and match.group(1) not in ("email", "mail", "send", "message", "to"):
                entities["recipient_name"] = match.group(1).strip().title()

        # Parse email subject and body if explicitly spoken e.g., "subject [subject] body [body]"
        subject_match = re.search(r"\bsubject\s+(?:is\s+)?(.*?)(?:\bbody\b|$)", text)
        if subject_match:
            entities["subject"] = subject_match.group(1).strip()
        
        body_match = re.search(r"\bbody\s+(?:is\s+)?(.*)$", text)
        if body_match:
            entities["body"] = body_match.group(1).strip()

        # Reminder Specifics
        # Extract time expressions: "in 30 minutes", "at 6 pm"
        time_match = re.search(r"\b(?:in|at|on|after)\b\s+(\d+\s+(?:minute|minutes|hour|hours|second|seconds|day|days)|\d+:\d+\s*(?:pm|am|pm\b|am\b)|\d+\s*(?:pm|am|pm\b|am\b))", text)
        if time_match:
            entities["time_expression"] = time_match.group(1).strip()
        
        # Extract reminder note: "remind me to [do something]"
        note_match = re.search(r"\bremind\s+(?:me\s+)?to\s+(.*?)(?:\bin\b|\bat\b|\bon\b|$)", text)
        if note_match:
            entities["reminder_note"] = note_match.group(1).strip()

        # Smart Home Specifics
        # Find action (on / off)
        action_match = re.search(r"\b(turn on|turn off|on|off|activate|deactivate|status|get status|set)\b", text)
        if action_match:
            action_raw = action_match.group(1)
            if "on" in action_raw or "activate" in action_raw:
                entities["device_action"] = "turn_on"
            elif "off" in action_raw or "deactivate" in action_raw:
                entities["device_action"] = "turn_off"
            elif "status" in action_raw:
                entities["device_action"] = "status"
            elif "set" in action_raw:
                entities["device_action"] = "set"

        # Find device: "light", "lights", "thermostat", "plug"
        device_match = re.search(r"\b(light|lights|thermostat|ac|heating|fan|lamp|plugs)\b", text)
        if device_match:
            entities["device_type"] = device_match.group(1).strip()
            # Normalize lights vs light
            if entities["device_type"] == "lights":
                entities["device_type"] = "light"

        # Find thermostat value if set
        temp_match = re.search(r"\b(?:to)\b\s+(\d+)\b", text)
        if temp_match and entities.get("device_type") in ("thermostat", "ac", "heating"):
            entities["device_value"] = int(temp_match.group(1))

        # Knowledge Specifics
        if intent == "general_knowledge":
            # Match "about [query]" or "search [query]" or "who is [query]"
            query_match = re.search(r"\b(?:about|search|wikipedia|who is|what is|define)\b\s+(.*)$", text)
            if query_match:
                entities["query"] = query_match.group(1).strip()
            else:
                # Default query is the whole input string clean of trigger keywords
                clean_query = re.sub(r"\b(wikipedia|search|for|tell|me|about|info|on)\b", "", text)
                entities["query"] = clean_query.strip()

        return entities
