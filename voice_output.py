"""Text-To-Speech (TTS) module for PyVoice Assistant.

Provides offline synthetic speech via pyttsx3, online high-quality speech via
gTTS, and visual terminal output fallback. Queues utterances to avoid overlaps.
"""

import os
import queue
import threading
import time
import logging
from typing import Optional
from gtts import gTTS

try:
    import playsound
    PLAYSOUND_AVAILABLE = True
except ImportError:
    PLAYSOUND_AVAILABLE = False


# Handle pyttsx3 import error or missing driver
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

logger = logging.getLogger("PyVoice.VoiceOutput")


class VoiceOutputManager:
    """Manages synthetic speech output with offline and online backends."""

    def __init__(self, 
                 engine_type: str = "offline", 
                 rate: int = 175, 
                 volume: float = 0.9, 
                 gender: str = "female"):
        """Initializes the TTS manager.

        Args:
            engine_type: "offline" or "online".
            rate: Speed of speech (words per minute).
            volume: Level (0.0 to 1.0).
            gender: "female" or "male".
        """
        self.engine_type = engine_type.lower()
        self.rate = rate
        self.volume = volume
        self.gender = gender.lower()

        self.speech_queue = queue.Queue()
        self.is_speaking = False
        self.tts_thread = None
        self.shutdown_flag = threading.Event()

        # Initialize pyttsx3 offline engine if selected
        self.offline_engine = None
        if PYTTSX3_AVAILABLE and self.engine_type == "offline":
            try:
                self.offline_engine = pyttsx3.init()
                self._configure_offline_engine()
            except Exception as e:
                logger.warning(f"Failed to initialize pyttsx3 engine: {e}. Defaulting to online/console.")
                self.engine_type = "online"

        # Start background speaking thread
        self.tts_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.tts_thread.start()

    def _configure_offline_engine(self):
        """Applies configured rate, volume, and gender to offline engine."""
        if not self.offline_engine:
            return
        
        try:
            self.offline_engine.setProperty('rate', self.rate)
            self.offline_engine.setProperty('volume', self.volume)
            
            # Select voice by gender
            voices = self.offline_engine.getProperty('voices')
            selected_voice = None
            if self.gender == "female":
                for voice in voices:
                    if "female" in voice.name.lower() or "zira" in voice.name.lower() or "david" not in voice.name.lower():
                        selected_voice = voice.id
                        break
            else:
                for voice in voices:
                    if "male" in voice.name.lower() or "david" in voice.name.lower():
                        selected_voice = voice.id
                        break
            
            if selected_voice:
                self.offline_engine.setProperty('voice', selected_voice)
            elif voices:
                self.offline_engine.setProperty('voice', voices[0].id)
        except Exception as e:
            logger.error(f"Error configuring pyttsx3 properties: {e}")

    def speak(self, text: str, block: bool = False):
        """Queues text to be spoken by the assistant.

        Args:
            text: Message to speak.
            block: If True, blocks execution until the utterance is fully spoken.
        """
        if not text:
            return
        
        # Log and print the text command visually (UI console representation)
        logger.info(f"Speaking: '{text}'")
        print(f"\n[Nova]: {text}")

        # Enqueue the phrase
        self.speech_queue.put(text)

        # Block if requested
        if block:
            while not self.speech_queue.empty() or self.is_speaking:
                time.sleep(0.05)

    def _process_queue(self):
        """Worker function running in a background thread to process speech events."""
        while not self.shutdown_flag.is_set():
            try:
                # Bounded timeout so loop checks shutdown_flag periodically
                text = self.speech_queue.get(timeout=0.2)
                self.is_speaking = True
                
                # Speak using configured engine
                if self.engine_type == "offline" and self.offline_engine:
                    self._speak_offline(text)
                else:
                    self._speak_online(text)

                self.speech_queue.task_done()
                self.is_speaking = False
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in speech thread worker: {e}")
                self.is_speaking = False

    def _speak_offline(self, text: str):
        """Synthesizes offline speech using pyttsx3."""
        try:
            # pyttsx3 requires calling say() then runAndWait()
            # Since we are running in a dedicated worker thread, runAndWait is safe
            self.offline_engine.say(text)
            self.offline_engine.runAndWait()
        except Exception as e:
            logger.error(f"pyttsx3 speech failed: {e}. Falling back to online gTTS...")
            self._speak_online(text)

    def _speak_online(self, text: str):
        """Synthesizes online speech using gTTS and plays it via playsound if available."""
        temp_audio = "temp_voice_output.mp3"
        try:
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(temp_audio)
            
            # Use playsound to play the mp3 if available
            if PLAYSOUND_AVAILABLE:
                playsound.playsound(temp_audio)
            else:
                logger.info("playsound module not available. Audio output only printed to terminal.")
        except Exception as e:
            logger.error(f"Online text-to-speech failed: {e}. Speech output only printed to terminal.")
        finally:
            if os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except Exception:
                    pass

    def stop(self):
        """Stops the speech thread and shuts down speaking operations."""
        self.shutdown_flag.set()
        # Empty speech queue
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
            except queue.Empty:
                break
        
        if self.tts_thread:
            self.tts_thread.join(timeout=1.0)
