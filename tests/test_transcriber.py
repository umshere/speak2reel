import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
from podcast_to_reels.transcriber import transcribe_audio, detect_language_fasttext, detect_language_langdetect

# Mock constants
FASTTEXT_MODEL_PATH = os.getenv("FASTTEXT_MODEL_PATH", "dummy_lid.176.bin")


@pytest.fixture
def mock_openai_transcribe():
    with patch('podcast_to_reels.transcriber.openai.Audio.transcribe') as mock_transcribe:
        mock_transcribe.return_value = { # Simulate verbose_json output
            "text": "This is a test transcription.",
            "language": "en",
            "segments": [
                {"text": "This is a test transcription.", "start": 0.0, "end": 2.5}
            ]
        }
        yield mock_transcribe

@pytest.fixture
def mock_fasttext():
    with patch('podcast_to_reels.transcriber.fasttext.load_model') as mock_load_model:
        model_instance = MagicMock()
        # Simulate fastText prediction: (('__label__en',), array([0.9]))
        model_instance.predict.return_value = (('__label__en',), MagicMock(spec=float, return_value=0.9))
        mock_load_model.return_value = model_instance
        yield mock_load_model, model_instance

@pytest.fixture
def mock_langdetect():
    with patch('podcast_to_reels.transcriber.detect') as mock_detect:
        mock_detect.return_value = "en" # langdetect typically returns 'en', 'es', etc.
        yield mock_detect

@pytest.fixture
def mock_file_operations():
    with patch('podcast_to_reels.transcriber.os.path.exists') as mock_exists, \
         patch('podcast_to_reels.transcriber.os.makedirs') as mock_makedirs, \
         patch('builtins.open', new_callable=mock_open) as mock_file_open:

        # Default: audio file exists, fasttext model exists by default for some tests
        mock_exists.side_effect = lambda path: path == "dummy_audio.mp3" or path == FASTTEXT_MODEL_PATH

        yield {
            "exists": mock_exists,
            "makedirs": mock_makedirs,
            "open": mock_file_open
        }

@pytest.fixture(autouse=True)
def mock_openai_api_key_env_var(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test_api_key")

# --- Tests for helper language detection functions ---
def test_detect_language_fasttext_success(mock_fasttext):
    _, model_instance = mock_fasttext
    lang = detect_language_fasttext("This is some English text.", model_instance)
    assert lang == "en"
    model_instance.predict.assert_called_once_with("This is some English text.", k=1)

def test_detect_language_fasttext_low_confidence(mock_fasttext):
    _, model_instance = mock_fasttext
    model_instance.predict.return_value = (('__label__de',), MagicMock(spec=float, return_value=0.3)) # Low confidence
    lang = detect_language_fasttext("Unsure text.", model_instance)
    assert lang is None

def test_detect_language_fasttext_exception(mock_fasttext):
    _, model_instance = mock_fasttext
    model_instance.predict.side_effect = Exception("FastText error")
    lang = detect_language_fasttext("Text.", model_instance)
    assert lang is None

def test_detect_language_fasttext_with_path_input(mock_fasttext):
    # This test is for the placeholder logic in detect_language_fasttext
    # if it's called with a path instead of text.
    _, model_instance = mock_fasttext
    lang = detect_language_fasttext("path/to/some/file.txt", model_instance)
    assert lang is None # Expect None due to path input and placeholder logic

def test_detect_language_langdetect_success(mock_langdetect):
    lang = detect_language_langdetect("This is some English text.")
    assert lang == "en"
    mock_langdetect.assert_called_once_with("This is some English text.")

def test_detect_language_langdetect_exception(mock_langdetect):
    from langdetect import lang_detect_exception
    mock_langdetect.side_effect = lang_detect_exception.LangDetectException("Langdetect error", 0)
    lang = detect_language_langdetect("Invalid text for langdetect.")
    assert lang is None

# --- Tests for main transcribe_audio function ---

def test_transcribe_audio_success_english_whisper_detection(
    mock_openai_transcribe, mock_fasttext, mock_langdetect, mock_file_operations
):
    audio_path = "dummy_audio.mp3"
    output_json_path = "output/transcription.json"

    success = transcribe_audio(audio_path, output_json_path, FASTTEXT_MODEL_PATH)

    assert success is True
    mock_openai_transcribe.assert_called_once() # Check if transcribe was called
    # Check if the output file was written to
    mock_file_operations["open"].assert_called_with(output_json_path, "w", encoding="utf-8")

    # Verify content written (simplified check)
    handle = mock_file_operations["open"].return_value
    # Get the first call to write()
    written_content = "".join(call_arg[0] for call_arg in handle.write.call_args_list)
    saved_data = json.loads(written_content)
    assert saved_data["language"] == "en"
    assert saved_data["text"] == "This is a test transcription."
    # FastText and Langdetect should not be called if Whisper detects language
    mock_fasttext[0].assert_called_once() # load_model is called
    mock_fasttext[1].predict.assert_not_called() # predict is not called
    mock_langdetect.assert_not_called()


def test_transcribe_audio_whisper_unknown_lang_fallback_to_fasttext(
    mock_openai_transcribe, mock_fasttext, mock_langdetect, mock_file_operations
):
    # Simulate Whisper returning an "unknown" language
    mock_openai_transcribe.return_value = {
        "text": "Ceci est un test.", "language": "unknown", # Whisper could not determine
        "segments": [{"text": "Ceci est un test.", "start": 0.0, "end": 2.0}]
    }
    # FastText will detect 'fr'
    mock_fasttext[1].predict.return_value = (('__label__fr',), MagicMock(spec=float, return_value=0.95))

    success = transcribe_audio("dummy_audio.mp3", "output/transcription.json", FASTTEXT_MODEL_PATH)
    assert success is True

    handle = mock_file_operations["open"].return_value
    written_content = "".join(call_arg[0] for call_arg in handle.write.call_args_list)
    saved_data = json.loads(written_content)

    assert saved_data["language"] == "fr" # FastText's detection
    mock_fasttext[1].predict.assert_called_once_with("Ceci est un test.", k=1)
    mock_langdetect.assert_not_called() # Langdetect should not be called if FastText succeeds


def test_transcribe_audio_fallback_to_langdetect(
    mock_openai_transcribe, mock_fasttext, mock_langdetect, mock_file_operations
):
    mock_openai_transcribe.return_value = {
        "text": "Ein Test.", "language": "unk", # Whisper unknown
        "segments": [{"text": "Ein Test.", "start": 0.0, "end": 1.5}]
    }
    # FastText fails (e.g. low confidence or error)
    mock_fasttext[1].predict.return_value = (('__label__de',), MagicMock(spec=float, return_value=0.1))
    # Langdetect will detect 'de'
    mock_langdetect.return_value = "de"

    success = transcribe_audio("dummy_audio.mp3", "output/transcription.json", FASTTEXT_MODEL_PATH)
    assert success is True
    saved_data = json.loads("".join(c[0] for c in mock_file_operations["open"].return_value.write.call_args_list))
    assert saved_data["language"] == "de" # Langdetect's detection
    mock_fasttext[1].predict.assert_called_once()
    mock_langdetect.assert_called_once_with("Ein Test.")


def test_transcribe_audio_no_language_detected(
    mock_openai_transcribe, mock_fasttext, mock_langdetect, mock_file_operations
):
    mock_openai_transcribe.return_value = {
        "text": "...", "language": "zxx", # Undetermined by Whisper
        "segments": [{"text": "...", "start": 0.0, "end": 1.0}]
    }
    mock_fasttext[1].predict.return_value = (('__label__ja',), MagicMock(spec=float, return_value=0.2)) # FastText low confidence
    mock_langdetect.side_effect = Exception("Langdetect failed") # Langdetect also fails

    success = transcribe_audio("dummy_audio.mp3", "output/transcription.json", FASTTEXT_MODEL_PATH)
    assert success is True # Still true, but language field might be missing or default
    saved_data = json.loads("".join(c[0] for c in mock_file_operations["open"].return_value.write.call_args_list))
    assert "language" not in saved_data or saved_data["language"] == "zxx" # Check if language field is absent or original unknown


def test_transcribe_audio_audio_file_not_found(mock_file_operations):
    mock_file_operations["exists"].side_effect = lambda path: path != "dummy_audio.mp3" # Audio file does not exist
    success = transcribe_audio("dummy_audio.mp3", "output/transcription.json", FASTTEXT_MODEL_PATH)
    assert success is False

def test_transcribe_audio_openai_api_error(mock_openai_transcribe, mock_file_operations):
    from openai import APIError # Import specific error type
    mock_openai_transcribe.side_effect = APIError("Simulated API Error", response=MagicMock(), body=None)
    success = transcribe_audio("dummy_audio.mp3", "output/transcription.json", FASTTEXT_MODEL_PATH)
    assert success is False

def test_transcribe_audio_fasttext_model_not_found(mock_openai_transcribe, mock_file_operations, mock_fasttext):
    # Simulate FastText model file not existing for loading
    original_exists_side_effect = mock_file_operations["exists"].side_effect
    def new_exists_side_effect(path):
        if path == FASTTEXT_MODEL_PATH:
            return False # Fasttext model does not exist
        return original_exists_side_effect(path)
    mock_file_operations["exists"].side_effect = new_exists_side_effect

    mock_fasttext[0].side_effect = FileNotFoundError # fasttext.load_model raises FileNotFoundError

    # Make Whisper language unknown to trigger fasttext attempt
    mock_openai_transcribe.return_value = {
        "text": "Some text", "language": "unknown",
        "segments": [{"text": "Some text", "start": 0.0, "end": 1.0}]
    }

    success = transcribe_audio("dummy_audio.mp3", "output/transcription.json", FASTTEXT_MODEL_PATH)
    # The function might still succeed if fastText is optional or if it prints a warning.
    # Based on current transcribe_audio, if fasttext model is required for lang detection and fails,
    # it might print an error and continue, or return False if it's critical.
    # The code in transcriber.py has a check: if os.path.exists(fasttext_model_path):
    # If this check is hit and it's false, it just skips fasttext.
    # Let's assume it proceeds without fasttext if model not found for lang detection part.
    # The FileNotFoundError is more likely if the load_model itself fails irrespective of the check.
    # The provided code actually tries to load the model *after* the check.
    # So if the check `os.path.exists(fasttext_model_path)` passes (mocked true initially)
    # but then `fasttext.load_model` fails, it will be caught by the general Exception.
    # Let's adjust the mock for the `load_model` to raise the FileNotFoundError

    # If fasttext.load_model raises FileNotFoundError, it should be caught.
    # The function should still return True because the transcription itself succeeded.
    # Language detection is an enhancement.
    assert success is True
    saved_data = json.loads("".join(c[0] for c in mock_file_operations["open"].return_value.write.call_args_list))
    # Language should be 'unknown' as fasttext failed and we didn't mock langdetect for this specific test path
    assert saved_data.get("language") == "unknown"


def test_transcribe_audio_no_openai_api_key(mock_file_operations, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    success = transcribe_audio("dummy_audio.mp3", "output/transcription.json", FASTTEXT_MODEL_PATH)
    assert success is False

def test_transcribe_audio_creates_output_directory(mock_openai_transcribe, mock_file_operations):
    audio_path = "dummy_audio.mp3"
    output_json_path = "new_output_dir/transcription.json"

    # Simulate output directory not existing initially
    def exists_side_effect(path):
        if path == audio_path: return True
        if path == FASTTEXT_MODEL_PATH: return True
        if path == "new_output_dir": return False # Dir does not exist
        return False
    mock_file_operations["exists"].side_effect = exists_side_effect

    success = transcribe_audio(audio_path, output_json_path, FASTTEXT_MODEL_PATH)

    assert success is True
    mock_file_operations["makedirs"].assert_called_once_with(os.path.dirname(output_json_path), exist_ok=True)

```
