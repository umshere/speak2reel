import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import requests
from podcast_to_reels.image_generator import generate_image_from_prompt


@pytest.fixture
def mock_openai_client():
    with patch('podcast_to_reels.image_generator.OpenAI') as mock_openai:
        client_mock = MagicMock()
        
        # Mock successful image generation response
        image_response_mock = MagicMock()
        image_response_mock.data = [MagicMock()]
        image_response_mock.data[0].url = "https://example.com/generated_image.png"
        
        client_mock.images.generate.return_value = image_response_mock
        
        # Mock chat completions for GPT-4o (fallback behavior)
        chat_response_mock = MagicMock()
        chat_response_mock.choices = [MagicMock()]
        chat_response_mock.choices[0].message.content = "GPT-4o response"
        client_mock.chat.completions.create.return_value = chat_response_mock
        
        mock_openai.return_value = client_mock
        yield {"openai": mock_openai, "client": client_mock}


@pytest.fixture
def mock_requests_get():
    with patch('podcast_to_reels.image_generator.requests.get') as mock_get:
        response_mock = MagicMock()
        response_mock.status_code = 200
        response_mock.content = b"dummy_image_bytes"
        response_mock.raise_for_status.return_value = None
        mock_get.return_value = response_mock
        yield mock_get


@pytest.fixture
def mock_file_operations():
    with patch('podcast_to_reels.image_generator.os.path.exists') as mock_exists, \
         patch('podcast_to_reels.image_generator.os.makedirs') as mock_makedirs, \
         patch('builtins.open', new_callable=mock_open) as mock_file:
        mock_exists.return_value = True  # Assume output directory exists by default
        yield {"exists": mock_exists, "makedirs": mock_makedirs, "open": mock_file}


@pytest.fixture(autouse=True)
def mock_openai_api_key_env_var(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test_openai_api_key")


def test_generate_image_success_dalle3(mock_openai_client, mock_requests_get, mock_file_operations):
    """Test successful image generation using DALL-E 3"""
    prompt = "A beautiful landscape"
    output_dir = "output/images"
    scene_index = 0
    expected_image_path = os.path.join(output_dir, f"scene_{scene_index}.png")

    success = generate_image_from_prompt(prompt, output_dir, scene_index)

    assert success is True
    
    # Verify OpenAI client was initialized with correct API key
    mock_openai_client["openai"].assert_called_once_with(api_key="test_openai_api_key")
    
    # Verify image generation was called
    mock_openai_client["client"].images.generate.assert_called_once()
    call_args = mock_openai_client["client"].images.generate.call_args[1]
    assert call_args["model"] == "dall-e-3"
    assert "landscape" in call_args["prompt"].lower()
    assert call_args["size"] == "1024x1792"
    assert call_args["quality"] == "standard"
    assert call_args["n"] == 1
    
    # Verify image was downloaded and saved
    mock_requests_get.assert_called_once_with("https://example.com/generated_image.png")
    mock_file_operations["open"].assert_called_once_with(expected_image_path, "wb")
    mock_file_operations["open"]().write.assert_called_once_with(b"dummy_image_bytes")


def test_generate_image_gpt4o_fallback(mock_openai_client, mock_requests_get, mock_file_operations):
    """Test that GPT-4o is attempted first, then falls back to DALL-E 3"""
    # Make GPT-4o throw an exception to trigger fallback
    mock_openai_client["client"].chat.completions.create.side_effect = Exception("GPT-4o not available")
    
    success = generate_image_from_prompt("test prompt", "output", 0)
    
    assert success is True
    # Should try GPT-4o first
    mock_openai_client["client"].chat.completions.create.assert_called_once()
    # Then fall back to DALL-E 3
    mock_openai_client["client"].images.generate.assert_called_once()


def test_generate_image_dir_creation(mock_openai_client, mock_requests_get, mock_file_operations):
    """Test that output directory is created if it doesn't exist"""
    mock_file_operations["exists"].return_value = False  # Output dir doesn't exist

    generate_image_from_prompt("prompt", "new_output_dir", 0)

    mock_file_operations["makedirs"].assert_called_once_with("new_output_dir")


def test_generate_image_no_api_key(monkeypatch, mock_openai_client):
    """Test failure when OpenAI API key is not set"""
    monkeypatch.delenv("OPENAI_API_KEY")
    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False
    mock_openai_client["openai"].assert_not_called()


def test_generate_image_empty_prompt(mock_openai_client):
    """Test failure with empty prompt"""
    success = generate_image_from_prompt("", "output", 0)
    assert success is False
    mock_openai_client["openai"].assert_not_called()


def test_generate_image_authentication_error(mock_openai_client, mock_requests_get, mock_file_operations):
    """Test handling of authentication errors"""
    mock_openai_client["client"].images.generate.side_effect = Exception("authentication failed")
    
    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False


def test_generate_image_content_policy_error(mock_openai_client, mock_requests_get, mock_file_operations):
    """Test handling of content policy violations"""
    mock_openai_client["client"].images.generate.side_effect = Exception("content policy violated")
    
    success = generate_image_from_prompt("inappropriate prompt", "output", 0)
    assert success is False


@patch('podcast_to_reels.image_generator.time.sleep', MagicMock())  # Mock time.sleep to speed up test
def test_generate_image_rate_limit_retry(mock_openai_client, mock_requests_get, mock_file_operations):
    """Test retry logic for rate limit errors"""
    # First call raises rate limit error, second succeeds
    mock_openai_client["client"].images.generate.side_effect = [
        Exception("rate limit exceeded"),
        mock_openai_client["client"].images.generate.return_value
    ]
    
    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is True
    assert mock_openai_client["client"].images.generate.call_count == 2


@patch('podcast_to_reels.image_generator.time.sleep', MagicMock())
def test_generate_image_server_error_all_retries_fail(mock_openai_client, mock_requests_get, mock_file_operations):
    """Test failure after all retries are exhausted"""
    mock_openai_client["client"].images.generate.side_effect = Exception("500 server error")
    
    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False
    assert mock_openai_client["client"].images.generate.call_count == 3  # Initial + 2 retries


def test_generate_image_download_error(mock_openai_client, mock_requests_get, mock_file_operations):
    """Test handling of image download errors"""
    mock_requests_get.side_effect = requests.exceptions.RequestException("Download failed")
    
    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False


def test_generate_image_file_saving_error(mock_openai_client, mock_requests_get, mock_file_operations):
    """Test handling of file saving errors"""
    mock_file_operations["open"].side_effect = IOError("Failed to save image")

    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False


def test_generate_image_makedirs_error(mock_openai_client, mock_requests_get, mock_file_operations):
    """Test handling of directory creation errors"""
    mock_file_operations["exists"].return_value = False
    mock_file_operations["makedirs"].side_effect = OSError("Permission denied")
    
    success = generate_image_from_prompt("prompt", "nonexistent/output", 0)
    assert success is False
