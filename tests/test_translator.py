import pytest
from unittest.mock import patch, MagicMock
import os
from podcast_to_reels.translator import translate_text

# Mock for OpenAI client and its methods
@pytest.fixture
def mock_openai_chat_completion():
    with patch('podcast_to_reels.translator.openai.OpenAI') as mock_openai_constructor:
        mock_client_instance = MagicMock()
        mock_openai_constructor.return_value = mock_client_instance

        mock_completion_response = MagicMock()
        mock_completion_response.choices = [MagicMock()]
        mock_completion_response.choices[0].message = MagicMock()
        mock_completion_response.choices[0].message.content = "Translated text here."

        mock_client_instance.chat.completions.create.return_value = mock_completion_response
        yield mock_client_instance.chat.completions.create

@pytest.fixture(autouse=True)
def mock_openai_api_key_env_var(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test_api_key")

def test_translate_text_success_with_source_language(mock_openai_chat_completion):
    text_to_translate = "Hola mundo"
    target_language = "en"
    source_language = "es"

    expected_prompt = f"Translate the following {source_language} text to {target_language}:\n\n{text_to_translate}"

    translated_text = translate_text(text_to_translate, target_language, source_language)

    assert translated_text == "Translated text here."
    mock_openai_chat_completion.assert_called_once()
    call_args = mock_openai_chat_completion.call_args[1] # Get kwargs
    assert call_args['model'] == "gpt-4o"
    assert call_args['messages'][-1]['role'] == "user"
    assert call_args['messages'][-1]['content'] == expected_prompt

def test_translate_text_success_without_source_language(mock_openai_chat_completion):
    text_to_translate = "Bonjour le monde"
    target_language = "en"

    expected_prompt = f"Translate the following text to {target_language}:\n\n{text_to_translate}"

    translated_text = translate_text(text_to_translate, target_language)

    assert translated_text == "Translated text here."
    mock_openai_chat_completion.assert_called_once()
    call_args = mock_openai_chat_completion.call_args[1]
    assert call_args['messages'][-1]['content'] == expected_prompt

def test_translate_text_empty_input(mock_openai_chat_completion):
    translated_text = translate_text("", "en")
    assert translated_text == ""
    mock_openai_chat_completion.assert_not_called()

def test_translate_text_no_api_key(monkeypatch, mock_openai_chat_completion):
    monkeypatch.delenv("OPENAI_API_KEY")
    translated_text = translate_text("Hello world", "es")
    assert translated_text is None
    mock_openai_chat_completion.assert_not_called()

def test_translate_text_openai_api_error(mock_openai_chat_completion):
    from openai import APIError # Import specific error type
    mock_openai_chat_completion.side_effect = APIError("Simulated API Error", response=MagicMock(), body=None)

    translated_text = translate_text("Hello world", "es")
    assert translated_text is None

def test_translate_text_openai_authentication_error(mock_openai_chat_completion):
    from openai import AuthenticationError # Import specific error type
    mock_openai_chat_completion.side_effect = AuthenticationError("Simulated Auth Error", response=MagicMock(), body=None)

    translated_text = translate_text("Hello world", "es")
    assert translated_text is None

def test_translate_text_openai_rate_limit_error(mock_openai_chat_completion):
    from openai import RateLimitError # Import specific error type
    mock_openai_chat_completion.side_effect = RateLimitError("Simulated Rate Limit Error", response=MagicMock(), body=None)

    translated_text = translate_text("Hello world", "es")
    assert translated_text is None

def test_translate_text_unexpected_error(mock_openai_chat_completion):
    mock_openai_chat_completion.side_effect = Exception("Unexpected error")

    translated_text = translate_text("Hello world", "es")
    assert translated_text is None

```
