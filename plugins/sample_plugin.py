"""Sample plugin for PyVoice Assistant.

Demonstrates the custom plugin interface by registering dice rolling and coin flipping
capabilities at startup.
"""

import random
import logging

logger = logging.getLogger("PyVoice.Plugins.SamplePlugin")


def roll_dice(entities=None, speak_fn=None, listen_fn=None) -> str:
    """Simulates rolling a six-sided dice."""
    result = random.randint(1, 6)
    return f"I rolled a dice and got a {result}."


def flip_coin(entities=None, speak_fn=None, listen_fn=None) -> str:
    """Simulates flipping a coin."""
    result = random.choice(["heads", "tails"])
    return f"I flipped a coin and it landed on {result}."


def register(assistant) -> None:
    """Dynamically registers capabilities with the assistant orchestrator.

    Args:
        assistant: The main VoiceAssistant orchestrator instance.
    """
    logger.info("Initializing Sample Plugin...")

    # Register custom intents and handlers directly on the assistant
    assistant.register_intent_handler("roll_dice", roll_dice)
    assistant.register_intent_handler("flip_coin", flip_coin)

    # Inject triggers to NLP classifier regex patterns
    if hasattr(assistant, 'nlp_engine') and assistant.nlp_engine:
        nlp = assistant.nlp_engine
        nlp.intent_patterns["roll_dice"] = [r"\b(roll a dice|roll dice|roll die|cast dice)\b"]
        nlp.intent_patterns["flip_coin"] = [r"\b(flip a coin|toss a coin|flip coin|toss coin)\b"]

    logger.info("Sample Plugin successfully registered 'roll_dice' and 'flip_coin' commands.")
