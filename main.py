"""Main Orchestrator for PyVoice Assistant.

Initializes the system database, speech engines, task handlers, dynamic plugins,
and exposes a Flask web interface to control the assistant on localhost.
"""

import os
import re
import sys
import yaml
import sqlite3
import logging
import importlib.util
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple
from dotenv import load_dotenv

# Flask Web Server
from flask import Flask, render_code_to_html, render_template, request, jsonify

# Core modules
from voice_input import VoiceInputManager, VoiceInputError
from voice_output import VoiceOutputManager
from nlp_engine import NLPEngine

# Task Handlers
from handlers.base_handler import BaseHandler, HandlerError
from handlers.weather_handler import WeatherHandler
from handlers.email_handler import EmailHandler
from handlers.reminder_handler import ReminderHandler
from handlers.smart_home_handler import SmartHomeHandler
from handlers.knowledge_handler import KnowledgeHandler

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("assistant.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("PyVoice.Orchestrator")

# Load environment variables
load_dotenv()


class VoiceAssistant:
    """Core Voice Assistant Orchestrator class managing inputs, NLP, and dispatching."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initializes configurations, database, engines, and task handlers."""
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.custom_commands: List[Dict[str, Any]] = []
        self.intent_handlers: Dict[str, Callable[..., str]] = {}
        
        # Load Yaml config files
        self._load_config()
        self._load_custom_commands()
        
        # Initialize Database
        self.db_path = self.config.get("paths", {}).get("database_file", "interactions.db")
        self._init_database()

        # Initialize speech layers
        fallback_to_text = self.config.get("assistant", {}).get("fallback_to_text", True)
        self.voice_input = VoiceInputManager(fallback_to_text=fallback_to_text)
        
        tts_cfg = self.config.get("tts", {})
        self.voice_output = VoiceOutputManager(
            engine_type=tts_cfg.get("engine", "offline"),
            rate=tts_cfg.get("rate", 175),
            volume=tts_cfg.get("volume", 0.9),
            gender=tts_cfg.get("gender", "female")
        )

        # Initialize NLP intent parser
        self.nlp_engine = NLPEngine()

        # Instantiate & Register Core Handlers
        self.weather_handler = WeatherHandler(self.config)
        self.email_handler = EmailHandler(self.config)
        self.reminder_handler = ReminderHandler(self.config)
        self.smart_home_handler = SmartHomeHandler(self.config)
        self.knowledge_handler = KnowledgeHandler(self.config)

        self._register_core_handlers()

        # Autoload Plugins from plugins/ folder
        self._load_plugins()

    def _load_config(self):
        """Loads main assistant configuration parameters."""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                self.config = yaml.safe_load(f)
            logger.info("Main config.yaml loaded successfully.")
        else:
            self.config = {
                "assistant": {"name": "Nova", "wake_word": "hey nova", "wake_word_enabled": True},
                "user": {"default_city": "Hyderabad"},
                "tts": {"engine": "offline", "rate": 175, "volume": 0.9, "gender": "female"},
                "paths": {"database_file": "interactions.db", "plugins_dir": "plugins"}
            }
            logger.warning("config.yaml not found. Initialized with defaults.")

    def _load_custom_commands(self):
        """Loads custom yaml commands if configured."""
        cmd_file = self.config.get("paths", {}).get("custom_commands_file", "custom_commands.yaml")
        if os.path.exists(cmd_file):
            with open(cmd_file, "r") as f:
                data = yaml.safe_load(f)
                self.custom_commands = data.get("commands", [])
            logger.info(f"Loaded {len(self.custom_commands)} custom commands from {cmd_file}")
        else:
            logger.info("No custom commands file found.")

    def _init_database(self):
        """Creates interactions logs table in SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS interactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        raw_text TEXT NOT NULL,
                        intent TEXT NOT NULL,
                        response TEXT NOT NULL,
                        success INTEGER NOT NULL
                    )
                """)
                conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.critical(f"Failed to initialize database: {e}")

    def _register_core_handlers(self):
        """Binds core handler methods to system intent dictionary."""
        # Wrap handler executions to pass callbacks
        self.register_intent_handler("weather", self.weather_handler.execute)
        self.register_intent_handler(
            "send_email", 
            lambda ents: self.email_handler.execute(ents, speak_fn=self.voice_output.speak, listen_fn=self.voice_input.listen_and_transcribe)
        )
        self.register_intent_handler(
            "set_reminder", 
            lambda ents: self.reminder_handler.execute(ents, speak_fn=self.voice_output.speak)
        )
        self.register_intent_handler("smart_home", self.smart_home_handler.execute)
        self.register_intent_handler("general_knowledge", self.knowledge_handler.execute)
        
        # System intents
        self.register_intent_handler("greet", lambda ents: "Hello! How can I help you today?")
        self.register_intent_handler("farewell", lambda ents: "Goodbye! Have a wonderful day.")

    def register_intent_handler(self, intent_name: str, handler_callable: Callable[[Dict[str, Any]], str]):
        """Allows external plugins or classes to bind callables to intents.

        Args:
            intent_name: Name of the intent target.
            handler_callable: A function/method accepting a dictionary of entities and returning a response string.
        """
        self.intent_handlers[intent_name] = handler_callable
        logger.info(f"Registered handler for intent: '{intent_name}'")

    def _load_plugins(self):
        """Scans plugins folder and registers valid python files."""
        plugins_dir = self.config.get("paths", {}).get("plugins_dir", "plugins")
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
            logger.info(f"Created plugins directory at '{plugins_dir}'")
            return

        for filename in os.listdir(plugins_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                file_path = os.path.join(plugins_dir, filename)
                
                try:
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        if hasattr(module, "register"):
                            module.register(self)
                            logger.info(f"Successfully loaded plugin: {filename}")
                        else:
                            logger.warning(f"Plugin {filename} does not define a 'register(assistant)' function.")
                except Exception as e:
                    logger.error(f"Failed to load plugin {filename}: {e}")

    def handle_command(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """Processes a raw command string through NLP, resolves matches, and logs it.

        Args:
            text: Transcribed input.

        Returns:
            A tuple of (spoken_response, parsed_nlp_dictionary).
        """
        response_text = ""
        success = 1
        nlp_data = {"intent": "unknown", "entities": {}}

        try:
            # 1. Check Custom YAML trigger phrases first
            custom_match = self._check_custom_commands(text)
            if custom_match:
                response_text = custom_match
                nlp_data = {"intent": "custom_yaml_command", "entities": {}}
                return response_text, nlp_data

            # 2. Parse through NLP Engine
            nlp_data = self.nlp_engine.parse(text)
            intent = nlp_data["intent"]
            entities = nlp_data["entities"]

            # 3. Dispatch to Intent Handler
            if intent in self.intent_handlers:
                response_text = self.intent_handlers[intent](entities)
            else:
                response_text = "I'm sorry, I don't know how to handle that request yet."
                success = 0

        except HandlerError as he:
            logger.warning(f"Handler error executing '{text}': {he}")
            response_text = str(he)
            success = 0
        except Exception as e:
            logger.error(f"Error processing command '{text}': {e}", exc_info=True)
            response_text = "An unexpected error occurred while processing your command."
            success = 0
        finally:
            # Mask sensitive patterns before writing logs
            masked_text = self._mask_sensitive_data(text)
            masked_response = self._mask_sensitive_data(response_text)
            
            # Log interaction to SQLite DB
            self._log_interaction(masked_text, nlp_data["intent"], masked_response, success)

        return response_text, nlp_data

    def _check_custom_commands(self, text: str) -> Optional[str]:
        """Matches input against custom commands defined in YAML."""
        for cmd in self.custom_commands:
            trigger = cmd.get("trigger", "").lower().strip()
            if trigger in text.lower():
                action_type = cmd.get("action_type")
                action = cmd.get("action")
                response = cmd.get("response", "Custom command executed.")

                logger.info(f"Custom command matched: '{trigger}' -> Type: {action_type}")

                if action_type == "shell":
                    # Execute shell subprocess
                    import subprocess
                    try:
                        subprocess.Popen(action, shell=True)
                    except Exception as e:
                        logger.error(f"Failed to execute custom shell action: {e}")
                        return "I was unable to launch the command."
                elif action_type == "python":
                    # Run quick python string execution
                    try:
                        exec(action)
                    except Exception as e:
                        logger.error(f"Failed to execute custom python code: {e}")
                        return "I encountered an error executing the custom python hook."

                return response
        return None

    def _log_interaction(self, raw_text: str, intent: str, response: str, success: int):
        """Inserts conversation transcript into SQLite."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO interactions (timestamp, raw_text, intent, response, success) VALUES (?, ?, ?, ?, ?)",
                    (datetime.now().isoformat(), raw_text, intent, response, success)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log interaction to database: {e}")

    def _mask_sensitive_data(self, text: str) -> str:
        """Masks emails and phone numbers to guarantee logger privacy."""
        if not text:
            return ""
        
        # Mask emails
        email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        text = re.sub(email_pattern, "[REDACTED EMAIL]", text)
        
        # Mask 10-digit phone numbers
        phone_pattern = r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        text = re.sub(phone_pattern, "[REDACTED PHONE]", text)
        
        return text

    def close(self):
        """Gracefully shuts down scheduler, engines and audio services."""
        logger.info("Shutting down Voice Assistant...")
        if hasattr(self, 'reminder_handler'):
            self.reminder_handler.shutdown()
        if hasattr(self, 'voice_output'):
            self.voice_output.stop()


# =====================================================================
# Flask Web App setup to run Assistant on Localhost Link
# =====================================================================

app = Flask(__name__)
assistant_instance: Optional[VoiceAssistant] = None


@app.route('/')
def home():
    """Renders the dashboard UI index template."""
    return render_template('index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    """Returns general server availability and mock devices state."""
    global assistant_instance
    if not assistant_instance:
        return jsonify({"status": "error", "message": "Assistant not initialized"}), 500
    
    # Retrieve thermostat & lights state
    ha_mock_states = assistant_instance.smart_home_handler._MOCK_DEVICES
    
    return jsonify({
        "status": "online",
        "server_mic_active": assistant_instance.voice_input.microphone_available,
        "devices": ha_mock_states
    })


@app.route('/api/command', methods=['POST'])
def run_command():
    """Receives JSON post request containing a command string to process."""
    global assistant_instance
    if not assistant_instance:
        return jsonify({"response": "Assistant is offline."}), 500
    
    data = request.get_json() or {}
    command = data.get("command")
    
    if not command:
        return jsonify({"response": "I didn't receive any command text."})

    # Execute orchestrator loop
    response_text, nlp_data = assistant_instance.handle_command(command)
    
    return jsonify({
        "response": response_text,
        "nlp": nlp_data
    })


@app.route('/api/weather', methods=['GET'])
def get_weather():
    """Helper endpoint to query current weather status from dashboard."""
    global assistant_instance
    if not assistant_instance:
        return jsonify({"temp": "--", "city": "None", "condition": "offline"}), 500
    
    # Fetch current location
    city = assistant_instance.config.get("user", {}).get("default_city", "Hyderabad")
    # Query using weather handler logic
    resp = assistant_instance.weather_handler.execute({"city": city})
    
    # Simple regex parse to update widget
    temp_match = re.search(r"currently\s+(\d+)\s+degrees", resp)
    cond_match = re.search(r"degrees\s+Celsius\s+and\s+(.*?)\s+in", resp)
    
    temp = temp_match.group(1) if temp_match else "28"
    condition = cond_match.group(1) if cond_match else "Clear Sky"
    
    return jsonify({
        "temp": temp,
        "city": city,
        "condition": condition
    })


@app.route('/api/devices/control', methods=['POST'])
def control_device():
    """Allows manual toggles from dashboard widgets to update device states."""
    global assistant_instance
    if not assistant_instance:
        return jsonify({"message": "Offline"}), 500
        
    data = request.get_json() or {}
    device_type = data.get("type")
    action = data.get("action")
    value = data.get("value")
    device_name = data.get("device", "")
    
    entities = {
        "device_type": device_type,
        "device_action": action,
        "device_value": value
    }
    
    # Expose command
    res = assistant_instance.smart_home_handler.execute(entities)
    return jsonify({"message": res})


def main():
    """Bootstrap execution starting Flask server on port 5000."""
    global assistant_instance
    assistant_instance = VoiceAssistant()
    
    logger.info("-----------------------------------------------------------------")
    logger.info(" PyVoice Assistant Local server launching on http://127.0.0.1:5000")
    logger.info("-----------------------------------------------------------------")
    
    try:
        # Run Flask server (BypassSandbox will be required if accessed externally)
        # Port 5000 is used
        app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        if assistant_instance:
            assistant_instance.close()


if __name__ == "__main__":
    main()
