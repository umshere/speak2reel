import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import time # For time.sleep mock if needed, though not directly mocked here
from podcast_to_reels.image_generator import generate_image_from_prompt

STABILITY_API_HOST = "https://api.stability.ai"
STABILITY_ENGINE_ID = "sd3-medium"

@pytest.fixture
def mock_requests_post():
    with patch('podcast_to_reels.image_generator.requests.post') as mock_post:
        response_mock = MagicMock()
        response_mock.status_code = 200
        response_mock.content = b"dummy_image_bytes"
        response_mock.json.return_value = {"message": "error details"} # For error cases
        response_mock.text = '{"message": "error details"}' # For error cases
        mock_post.return_value = response_mock
        yield mock_post

@pytest.fixture
def mock_file_operations_for_image_gen():
    with patch('podcast_to_reels.image_generator.os.path.exists') as mock_exists, \
         patch('podcast_to_reels.image_generator.os.makedirs') as mock_makedirs, \
         patch('builtins.open', new_callable=mock_open) as mock_file:
        mock_exists.return_value = True # Assume output directory exists by default
        yield {"exists": mock_exists, "makedirs": mock_makedirs, "open": mock_file}

@pytest.fixture(autouse=True)
def mock_stability_api_key_env_var(monkeypatch):
    monkeypatch.setenv("STABILITY_API_KEY", "test_stability_api_key")


def test_generate_image_success(mock_requests_post, mock_file_operations_for_image_gen):
    prompt = "A beautiful landscape"
    output_dir = "output/images"
    scene_index = 0
    expected_image_path = os.path.join(output_dir, f"scene_{scene_index}.png")

    success = generate_image_from_prompt(prompt, output_dir, scene_index)

    assert success is True
    mock_requests_post.assert_called_once()
    call_args = mock_requests_post.call_args

    # Check URL
    assert call_args[0][0] == f"{STABILITY_API_HOST}/v2beta/stable-image/generate/sd3"
    # Check headers
    headers = call_args[1]['headers']
    assert headers["Authorization"] == "Bearer test_stability_api_key"
    assert headers["Accept"] == "image/png"
    # Check files (multipart/form-data payload)
    files_payload = call_args[1]['files']
    assert files_payload["prompt"] == (None, prompt)
    assert files_payload["aspect_ratio"] == (None, "9:16")
    assert files_payload["output_format"] == (None, "png")
    assert files_payload["model"] == (None, STABILITY_ENGINE_ID)

    mock_file_operations_for_image_gen["open"].assert_called_once_with(expected_image_path, "wb")
    mock_file_operations_for_image_gen["open"]().write.assert_called_once_with(b"dummy_image_bytes")

def test_generate_image_dir_creation(mock_requests_post, mock_file_operations_for_image_gen):
    mock_file_operations_for_image_gen["exists"].return_value = False # Output dir doesn't exist

    generate_image_from_prompt("prompt", "new_output_dir", 0)

    mock_file_operations_for_image_gen["makedirs"].assert_called_once_with("new_output_dir", exist_ok=True)


def test_generate_image_no_api_key(monkeypatch, mock_requests_post):
    monkeypatch.delenv("STABILITY_API_KEY")
    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False
    mock_requests_post.assert_not_called()

def test_generate_image_empty_prompt(mock_requests_post):
    success = generate_image_from_prompt("", "output", 0)
    assert success is False
    mock_requests_post.assert_not_called()

def test_generate_image_api_401_authentication_error(mock_requests_post):
    mock_requests_post.return_value.status_code = 401
    mock_requests_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_requests_post.return_value)

    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False
    assert mock_requests_post.call_count == 1 # No retries for 401

def test_generate_image_api_403_forbidden_error(mock_requests_post):
    mock_requests_post.return_value.status_code = 403
    mock_requests_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_requests_post.return_value)

    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False
    assert mock_requests_post.call_count == 1

def test_generate_image_api_400_bad_request_error(mock_requests_post):
    mock_requests_post.return_value.status_code = 400
    mock_requests_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_requests_post.return_value)

    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False
    assert mock_requests_post.call_count == 1

@patch('podcast_to_reels.image_generator.time.sleep', MagicMock()) # Mock time.sleep to speed up test
def test_generate_image_api_500_server_error_with_retry(mock_requests_post):
    # First two calls raise 500, third call succeeds
    response_success = MagicMock()
    response_success.status_code = 200
    response_success.content = b"dummy_image_bytes"

    error_response = MagicMock()
    error_response.status_code = 500
    error_response.json.return_value = {"message": "server error"}
    error_response.text = '{"message": "server error"}'

    mock_requests_post.side_effect = [
        requests.exceptions.HTTPError(response=error_response), # triggers raise_for_status
        requests.exceptions.HTTPError(response=error_response), # triggers raise_for_status
        response_success
    ]
    # Manually set up raise_for_status for the error responses
    error_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=error_response)


    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is True
    assert mock_requests_post.call_count == 3 # Initial call + 2 retries
    assert time.sleep.call_count == 2 # Called before each retry


@patch('podcast_to_reels.image_generator.time.sleep', MagicMock())
def test_generate_image_api_500_server_error_all_retries_fail(mock_requests_post):
    error_response = MagicMock()
    error_response.status_code = 500
    error_response.json.return_value = {"message": "server error"}
    error_response.text = '{"message": "server error"}'
    error_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=error_response)

    mock_requests_post.return_value = error_response # All calls return this

    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False
    assert mock_requests_post.call_count == 3 # Initial call + 2 retries
    assert time.sleep.call_count == 2

def test_generate_image_requests_exception_network_error(mock_requests_post):
    import requests # Ensure requests is imported for the exception
    mock_requests_post.side_effect = requests.exceptions.RequestException("Network error")

    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False
    assert mock_requests_post.call_count == 3 # Retries for general RequestException too

def test_generate_image_file_saving_error(mock_requests_post, mock_file_operations_for_image_gen):
    mock_file_operations_for_image_gen["open"].side_effect = IOError("Failed to save image")

    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False

def test_generate_image_unexpected_error(mock_requests_post):
    mock_requests_post.side_effect = Exception("Totally unexpected")
    success = generate_image_from_prompt("prompt", "output", 0)
    assert success is False

```
