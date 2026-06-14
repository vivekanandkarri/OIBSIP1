"""Speech recognition module for PyVoice Assistant.

Handles audio capture, ambient noise calibration, transcribing via Google Speech
API, and fallback to OpenAI Whisper API.
"""

import os
import logging
from typing import Optional
import speech_recognition as sr
from openai import OpenAI

logger = logging.getLogger("PyVoice.VoiceInput")


class VoiceInputError(Exception):
    """Custom exception raised when speech recognition fails completely."""
    pass


class VoiceInputManager:
    """Manages audio capture and transcription with multi-engine fallback."""

    def __init__(self, fallback_to_text: bool = True):
        """Initializes the voice input manager.

        Args:
            fallback_to_text: If True, falls back to console input when mic/audio fails.
        """
        self.recognizer = sr.Recognizer()
        self.fallback_to_text = fallback_to_text
        self.microphone_available = True

        # Test if microphone is available
        try:
            with sr.Microphone() as source:
                # Adjusting for ambient noise initially
                logger.info("Calibrating microphone for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        except Exception as e:
            logger.warning(f"No microphone detected or permission denied: {e}. Fallback to text: {fallback_to_text}")
            self.microphone_available = False

    def listen_and_transcribe(self, timeout: float = 5.0, phrase_time_limit: float = 10.0) -> str:
        """Listens from the microphone and returns the transcribed text.

        Attempts Google Speech Recognition first. If it fails due to network or recognition
        errors and an OpenAI API key is configured, falls back to OpenAI Whisper.

        Args:
            timeout: Maximum time to wait for a phrase to start (seconds).
            phrase_time_limit: Maximum time to record a phrase (seconds).

        Returns:
            The transcribed text as a string in lowercase.

        Raises:
            VoiceInputError: If speech capture or transcription fails completely.
        """
        # If microphone is not available and text fallback is enabled, read from standard input
        if not self.microphone_available:
            if self.fallback_to_text:
                print("\n[Nova is listening - type your command below]")
                try:
                    text = input("> ")
                    return text.strip().lower()
                except (KeyboardInterrupt, EOFError):
                    raise VoiceInputError("Input stream closed by user.")
            else:
                raise VoiceInputError("Microphone not available and text fallback is disabled.")

        try:
            with sr.Microphone() as source:
                logger.info("Listening...")
                # Capture ambient noise level on each turn slightly
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            raise VoiceInputError("Listening timed out waiting for phrase.")
        except Exception as e:
            logger.error(f"Error accessing microphone: {e}")
            if self.fallback_to_text:
                logger.info("Attempting console text input fallback...")
                print("\n[Microphone Error - type your command below]")
                try:
                    text = input("> ")
                    return text.strip().lower()
                except (KeyboardInterrupt, EOFError):
                    pass
            raise VoiceInputError(f"Failed to access microphone: {e}")

        # Attempt transcription
        return self._transcribe_audio(audio)

    def _transcribe_audio(self, audio: sr.AudioData) -> str:
        """Internal helper to transcribe audio using multiple services."""
        # 1. Attempt Google Speech Recognition (free, no credentials needed)
        try:
            logger.info("Transcribing using Google Speech API...")
            text = self.recognizer.recognize_google(audio)
            logger.info(f"Google transcription: '{text}'")
            return text.strip().lower()
        except sr.UnknownValueError:
            logger.warning("Google Speech API could not understand the audio.")
        except (sr.RequestError, Exception) as e:
            logger.warning(f"Google Speech API request failed: {e}. Trying fallback Whisper...")

        # 2. Attempt OpenAI Whisper API Fallback if key exists
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                logger.info("Attempting Whisper API fallback...")
                # Write audio data to a temporary wav file
                temp_wav = "temp_voice_input.wav"
                with open(temp_wav, "wb") as f:
                    f.write(audio.get_wav_data())

                client = OpenAI(api_key=openai_key)
                with open(temp_wav, "rb") as audio_file:
                    transcript_res = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                
                # Cleanup temp file
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)

                text = transcript_res.text
                logger.info(f"Whisper transcription: '{text}'")
                return text.strip().lower()
            except Exception as whisper_err:
                logger.error(f"Whisper API transcription failed: {whisper_err}")
                if os.path.exists(temp_wav):
                    try:
                        os.remove(temp_wav)
                    except Exception:
                        pass
        
        raise VoiceInputError("Unrecognized speech. Google and Whisper transcription both failed or were unavailable.")
