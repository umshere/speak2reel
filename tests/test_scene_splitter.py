import pytest
from unittest.mock import patch, MagicMock
import os
from podcast_to_reels.scene_splitter import split_transcript_into_scenes, generate_image_prompt_with_openai

@pytest.fixture
def mock_openai_chat_completion_for_prompts():
    with patch('podcast_to_reels.scene_splitter.openai.OpenAI') as mock_openai_constructor:
        mock_client_instance = MagicMock()
        mock_openai_constructor.return_value = mock_client_instance

        mock_completion_response = MagicMock()
        mock_completion_response.choices = [MagicMock()]
        mock_completion_response.choices[0].message = MagicMock()
        # Default mock prompt, can be changed per test
        mock_completion_response.choices[0].message.content = "Generated English prompt."

        mock_client_instance.chat.completions.create.return_value = mock_completion_response
        yield mock_client_instance.chat.completions.create

@pytest.fixture(autouse=True)
def mock_openai_api_key_env_var(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test_api_key")

# --- Tests for generate_image_prompt_with_openai ---

def test_generate_image_prompt_success_english_input(mock_openai_chat_completion_for_prompts):
    text_chunk = "A cat sitting on a mat."
    language = "en"
    expected_system_prompt = "You are an expert prompt generator for AI image creation, specializing in modern flat-style illustrations. Ensure all output prompts are in English."
    expected_user_prompt = (
        "Based on the following English text, generate a concise and visually descriptive English prompt for an AI image generator. "
        "The prompt should be suitable for creating a modern flat-style illustration. "
        f"Text: '{text_chunk}'"
    )

    prompt = generate_image_prompt_with_openai(text_chunk, language)

    assert prompt == "Generated English prompt."
    mock_openai_chat_completion_for_prompts.assert_called_once()
    call_args = mock_openai_chat_completion_for_prompts.call_args[1]
    assert call_args['model'] == "gpt-4o-mini"
    assert call_args['messages'][0]['role'] == "system"
    assert call_args['messages'][0]['content'] == expected_system_prompt
    assert call_args['messages'][1]['role'] == "user"
    assert call_args['messages'][1]['content'] == expected_user_prompt

def test_generate_image_prompt_success_non_english_input(mock_openai_chat_completion_for_prompts):
    text_chunk = "Un gato sentado en una alfombra."
    language = "es"
    expected_user_prompt = (
        f"Based on the following text (which is in {language}), generate a concise and visually descriptive English prompt for an AI image generator. "
        "The prompt should be suitable for creating a modern flat-style illustration. "
        "If the text is not in English, understand its meaning and generate an English prompt that captures the essence for the illustration. "
        f"Text: '{text_chunk}'"
    )
    prompt = generate_image_prompt_with_openai(text_chunk, language)
    assert prompt == "Generated English prompt."
    call_args = mock_openai_chat_completion_for_prompts.call_args[1]
    assert call_args['messages'][1]['content'] == expected_user_prompt


def test_generate_image_prompt_api_error(mock_openai_chat_completion_for_prompts):
    from openai import APIError
    mock_openai_chat_completion_for_prompts.side_effect = APIError("Simulated API Error", response=MagicMock(), body=None)
    prompt = generate_image_prompt_with_openai("Some text", "en")
    assert prompt is None

def test_generate_image_prompt_no_api_key(monkeypatch, mock_openai_chat_completion_for_prompts):
    monkeypatch.delenv("OPENAI_API_KEY")
    prompt = generate_image_prompt_with_openai("Some text", "en")
    assert prompt is None
    mock_openai_chat_completion_for_prompts.assert_not_called()

def test_generate_image_prompt_strips_prompt_prefix(mock_openai_chat_completion_for_prompts):
    mock_openai_chat_completion_for_prompts.return_value.choices[0].message.content = "Prompt: A cool image."
    prompt = generate_image_prompt_with_openai("text", "en")
    assert prompt == "A cool image."


# --- Tests for split_transcript_into_scenes ---

@pytest.fixture
def sample_transcript_data_en():
    return {
        "language": "en",
        "segments": [
            {"text": "Hello everyone and welcome back to the podcast.", "start": 0.5, "end": 3.5}, # 8 words
            {"text": "Today we're talking about the future of AI.", "start": 3.8, "end": 6.9}, # 9 words
            {"text": "It's a rapidly evolving field with many exciting developments.", "start": 7.2, "end": 11.5}, # 10 words
            {"text": "Let's dive into some of the latest trends.", "start": 12.0, "end": 14.5} # 8 words
        ]
    }

def test_split_transcript_basic_chunking(sample_transcript_data_en, mock_openai_chat_completion_for_prompts):
    # words_per_chunk = 20.
    # Scene 1: "Hello ... podcast. Today ... AI." (8 + 9 = 17 words)
    # Scene 2: "It's a ... developments. Let's ... trends." (10 + 8 = 18 words)

    scenes = split_transcript_into_scenes(sample_transcript_data_en, words_per_chunk=15) # Lower target for clearer splits

    assert len(scenes) == 2
    mock_openai_chat_completion_for_prompts.call_count == 2

    # Scene 1
    assert scenes[0]['chunk_text'] == "Hello everyone and welcome back to the podcast. Today we're talking about the future of AI."
    assert scenes[0]['start_time'] == 0.5
    assert scenes[0]['end_time'] == 6.9 # End time of the second segment
    assert scenes[0]['image_prompt'] == "Generated English prompt."

    # Scene 2
    assert scenes[1]['chunk_text'] == "It's a rapidly evolving field with many exciting developments. Let's dive into some of the latest trends."
    assert scenes[1]['start_time'] == 7.2
    assert scenes[1]['end_time'] == 14.5
    assert scenes[1]['image_prompt'] == "Generated English prompt."

def test_split_transcript_single_long_segment_forms_own_scene(mock_openai_chat_completion_for_prompts):
    transcript = {
        "language": "en",
        "segments": [
            {"text": "This is a single very long segment that definitely exceeds the typical target words per chunk by a large margin.", "start": 0.0, "end": 10.0} # 20 words
        ]
    }
    # words_per_chunk = 10. segment_word_count (20) >= 10 * 1.5 (15) is true
    scenes = split_transcript_into_scenes(transcript, words_per_chunk=10)
    assert len(scenes) == 1
    assert scenes[0]['chunk_text'] == transcript["segments"][0]["text"]
    assert scenes[0]['start_time'] == 0.0
    assert scenes[0]['end_time'] == 10.0
    mock_openai_chat_completion_for_prompts.assert_called_once()


def test_split_transcript_respects_max_words_per_chunk_plus_threshold(mock_openai_chat_completion_for_prompts):
    transcript = {
        "language": "en",
        "segments": [
            {"text": "One two three four five six seven eight nine ten.", "start": 0.0, "end": 5.0}, # 10 words
            {"text": "Eleven twelve thirteen fourteen fifteen sixteen seventeen.", "start": 5.5, "end": 10.0}, # 7 words
            {"text": "Eighteen nineteen twenty twentyone twentytwo.", "start": 10.5, "end": 15.0} # 5 words
        ]
    }
    # words_per_chunk = 10.
    # Chunk 1: seg1 (10 words). current_chunk_word_count = 10.
    # Next seg2 (7 words). 10 + 7 = 17. 17 > 10 + 5 (15) is true. So seg1 forms a chunk.
    # Chunk 2: seg2 (7 words). current_chunk_word_count = 7.
    # Next seg3 (5 words). 7 + 5 = 12. 12 > 10 + 5 (15) is false. seg2 + seg3 forms a chunk.
    scenes = split_transcript_into_scenes(transcript, words_per_chunk=10)
    assert len(scenes) == 2
    assert scenes[0]['chunk_text'] == "One two three four five six seven eight nine ten."
    assert scenes[0]['start_time'] == 0.0
    assert scenes[0]['end_time'] == 5.0

    assert scenes[1]['chunk_text'] == "Eleven twelve thirteen fourteen fifteen sixteen seventeen. Eighteen nineteen twenty twentyone twentytwo."
    assert scenes[1]['start_time'] == 5.5
    assert scenes[1]['end_time'] == 15.0
    assert mock_openai_chat_completion_for_prompts.call_count == 2


def test_split_transcript_empty_or_malformed_data():
    assert split_transcript_into_scenes({}, words_per_chunk=15) == []
    assert split_transcript_into_scenes({"segments": []}, words_per_chunk=15) == []
    assert split_transcript_into_scenes({"language": "en"}, words_per_chunk=15) == []


def test_split_transcript_segments_without_text(mock_openai_chat_completion_for_prompts):
    transcript = {
        "language": "en",
        "segments": [
            {"text": "Valid segment.", "start": 0.0, "end": 1.0},
            {"text": "", "start": 1.0, "end": 2.0}, # Empty text segment
            {"text": None, "start": 2.0, "end": 3.0}, # None text segment
            {"text": "Another valid segment.", "start": 3.0, "end": 4.0"}
        ]
    }
    scenes = split_transcript_into_scenes(transcript, words_per_chunk=5)
    assert len(scenes) == 2 # Two scenes from the two valid segments
    assert scenes[0]['chunk_text'] == "Valid segment."
    assert scenes[1]['chunk_text'] == "Another valid segment."
    assert mock_openai_chat_completion_for_prompts.call_count == 2

def test_split_transcript_prompt_generation_failure(sample_transcript_data_en, mock_openai_chat_completion_for_prompts):
    mock_openai_chat_completion_for_prompts.side_effect = Exception("Failed to generate prompt")
    scenes = split_transcript_into_scenes(sample_transcript_data_en, words_per_chunk=15)

    assert len(scenes) == 2 # Still creates scenes
    assert scenes[0]['image_prompt'] is None # Prompt generation failed
    assert scenes[1]['image_prompt'] is None

```
