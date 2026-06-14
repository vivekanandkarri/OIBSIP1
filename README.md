# PyVoice Assistant (Nova Dashboard)

PyVoice Assistant (named **Nova**) is a modular, event-driven voice assistant written in Python 3.10+. It features a premium, responsive Web Dashboard running on a local Flask server (`http://localhost:5000`) for visually interacting with Nova, monitoring NLP intent parsing, checking simulated smart home states, and managing background timer jobs.

---

## 🛠️ Features

1. **Speech Recognition**: Uses the standard `SpeechRecognition` engine with Google Speech API as primary and OpenAI Whisper API as a secure network fallback.
2. **Text-To-Speech**: Low-latency offline speech utilizing `pyttsx3`, online speech utilizing `gTTS` + `playsound`, and browser-based Web Speech API fallback.
3. **Intent Engine**: Tokenizes and extracts entities (GPE cities, person names, dates) using `spaCy` (`en_core_web_sm`) and custom regex slot-fillers.
4. **Interactive Dashboard**: Sleek dark-mode interface with glassmorphism panels, microphone button pulse animations, dynamic smart home widget sliders, and live intent logs.
5. **SQLite Interaction Logging**: Automatically logs conversations, matching intents, and results into a local `interactions.db` table. Phone numbers and email addresses are automatically masked.
6. **Autoloaded Plugins**: Any Python file placed in the `plugins/` directory containing a `register(assistant)` function is loaded at startup.
7. **Custom CLI Triggers**: Custom YAML commands mapped to launch local executable programs (e.g. `notepad.exe`) or run arbitrary python lines.

---

## 📁 Project Structure

```
pyvoice_assistant/
│
├── .env.example                # Example environment keys
├── config.yaml                 # Main user preferences & settings
├── custom_commands.yaml        # Keyphrase mapped to shell/python commands
├── requirements.txt            # Python dependencies (pinned)
├── README.md                   # Setup guide
├── main.py                     # Main Orchestrator & Local Flask Server
├── voice_input.py              # Speech Recognition module
├── voice_output.py             # TTS Audio speaker
├── nlp_engine.py               # NLP intent classifier
│
├── templates/
│   └── index.html              # HTML structure of Dashboard
├── static/
│   ├── css/
│   │   └── style.css           # Premium layout style rules
│   └── js/
│       └── app.js              # Browser Speech/API dashboard logic
│
├── handlers/                   # Core capability task handlers
│   ├── __init__.py
│   ├── base_handler.py
│   ├── weather_handler.py
│   ├── email_handler.py
│   ├── reminder_handler.py
│   ├── smart_home_handler.py
│   └── knowledge_handler.py
│
├── plugins/                    # Extensibility directory
│   ├── __init__.py
│   └── sample_plugin.py        # Demo plugin (roll_dice, flip_coin)
│
└── tests/                      # Automated test suite (pytest)
    ├── __init__.py
    ├── test_voice.py
    ├── test_nlp.py
    └── test_handlers.py
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
Ensure you have Python 3.10 or 3.11 installed.

### 2. Install Dependencies
Clone this repository or move to the project directory, then run:
```bash
pip install -r requirements.txt
```

> [!NOTE]
> spaCy requires its English small model `en_core_web_sm`. If the requirements file wheel URL installation is blocked or fails, you can download it manually with:
> `python -m spacy download en_core_web_sm`

### 3. Environment Secrets Configuration
Rename `.env.example` to `.env` and fill in API keys to unlock advanced capability integrations:
- `OPENWEATHER_API_KEY`: Weather reports.
- `SENDER_EMAIL` & `SENDER_PASSWORD`: Compose and dispatch actual SMTP emails.
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`: Factual Conversational Agent lookups.
- `HOME_ASSISTANT_TOKEN`: Real Home Assistant REST commands.

*If no keys are provided, Nova operates in simulated/mock mode, allowing you to test interactions completely safely without external configuration.*

### 4. Configuration Preferences
Modify `config.yaml` to adjust Nova's voice rate speed, default locations, engine types, and gender.

---

## 🖥️ Running the Assistant (Localhost link)

To launch the dashboard server, execute the main file:
```bash
python main.py
```

Nova will output the startup log and list the active link:
```
-----------------------------------------------------------------
 PyVoice Assistant Local server launching on http://127.0.0.1:5000
-----------------------------------------------------------------
```

Open **`http://localhost:5000`** in your web browser. 

### Interacting with Nova
- **Voice**: Click the glowing microphone button. Speak a command (e.g. *"What is the weather in Paris?"*, *"Set a reminder to study in 10 seconds"*, *"Turn on the bedroom light"*).
- **Text**: Type commands in the console input bar and press Enter.
- **Mock Widgets**: Slide the thermostat scale or click the lights toggle switches. Nova will update state locally and output responses to the dashboard conversation panel.

---

## 🧪 Running Automated Unit Tests

Ensure `pytest` is installed. Run the test suite:
```bash
pytest tests/
```
All tests check mock operations, mock inputs, and speech queue parameters, verifying execution safety and PEP 8 conformity.
