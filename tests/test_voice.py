"""Unit tests for PyVoice Speech Recognition and Text-To-Speech modules.

Uses pytest to mock microphone triggers, transcription engines, and audio players.
"""

import pytest
from unittest.mock import MagicMock, patch
from voice_input import VoiceInputManager, VoiceInputError
from voice_output import VoiceOutputManager


class TestVoiceInput:
    """Validates voice input capture operations and multi-service fallbacks."""

    @patch('speech_recognition.Microphone')
    @patch('speech_recognition.Recognizer')
    def test_init_calibration_success(self, mock_rec_class, mock_mic_class):
        """Ensures system calibrates for ambient noise during setup."""
        mock_rec = mock_rec_class.return_value
        manager = VoiceInputManager(fallback_to_text=False)
        
        assert manager.microphone_available is True
        mock_rec.adjust_for_ambient_noise.assert_called_once()

    @patch('speech_recognition.Microphone', side_effect=Exception("No device"))
    def test_init_calibration_fail_fallback_text(self, mock_mic_class):
        """Ensures microphone failures flag the text input fallback."""
        manager = VoiceInputManager(fallback_to_text=True)
        assert manager.microphone_available is False

    @patch('speech_recognition.Microphone')
    @patch('speech_recognition.Recognizer')
    def test_transcribe_google_success(self, mock_rec_class, mock_mic_class):
        """Tests standard successful transcription via Google Speech API."""
        mock_rec = mock_rec_class.return_value
        mock_rec.recognize_google.return_value = "Hello Nova"
        
        manager = VoiceInputManager(fallback_to_text=False)
        result = manager.listen_and_transcribe()
        
        assert result == "hello nova"
        mock_rec.recognize_google.assert_called_once()


class TestVoiceOutput:
    """Verifies synthesis, volume settings, and thread queues."""

    @patch('pyttsx3.init')
    def test_offline_tts_speak_queues(self, mock_pyttsx_init):
        """Validates that spoken messages are added to the speech thread queue."""
        mock_engine = MagicMock()
        mock_pyttsx_init.return_value = mock_engine
        
        # Initialize output manager
        output = VoiceOutputManager(engine_type="offline")
        
        # Test speaking adds to queue
        with patch.object(output.speech_queue, 'put') as mock_put:
            output.speak("Test voice queue")
            mock_put.assert_called_once_with("Test voice queue")
        
        output.stop()
