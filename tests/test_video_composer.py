import pytest
from unittest.mock import patch, MagicMock, mock_open, call
import os
import numpy as np # For dummy audio/image data if needed by mocks
from podcast_to_reels.video_composer import generate_srt_from_transcript, compose_video, format_srt_timestamp

# --- Mocks for MoviePy objects ---
@pytest.fixture
def mock_moviepy_clips():
    # This fixture provides mocks for all MoviePy classes used.
    # Individual methods on these instances will be mocked as needed within tests.
    with patch('podcast_to_reels.video_composer.AudioFileClip') as MockAudioFileClip, \
         patch('podcast_to_reels.video_composer.ImageClip') as MockImageClip, \
         patch('podcast_to_reels.video_composer.TextClip') as MockTextClip, \
         patch('podcast_to_reels.video_composer.CompositeVideoClip') as MockCompositeVideoClip:

        # Configure default behaviors for mocked MoviePy objects
        mock_audio_instance = MockAudioFileClip.return_value
        mock_audio_instance.duration = 10.0 # Default audio duration
        mock_audio_instance.close = MagicMock()

        mock_image_instance = MockImageClip.return_value
        mock_image_instance.set_duration.return_value = mock_image_instance
        mock_image_instance.set_start.return_value = mock_image_instance
        mock_image_instance.resize.return_value = mock_image_instance
        mock_image_instance.crop.return_value = mock_image_instance
        mock_image_instance.size = [1080,1920] # After resize/crop
        mock_image_instance.w = 1080
        mock_image_instance.h = 1920
        mock_image_instance.start = 0.0
        mock_image_instance.end = 0.0 # Will be updated by set_duration
        mock_image_instance.close = MagicMock()

        # Make set_duration update .end attribute
        def mock_set_duration(duration_val):
            mock_image_instance.end = mock_image_instance.start + duration_val
            return mock_image_instance
        mock_image_instance.set_duration.side_effect = mock_set_duration


        mock_text_instance = MockTextClip.return_value
        mock_text_instance.set_position.return_value = mock_text_instance
        mock_text_instance.set_duration.return_value = mock_text_instance
        mock_text_instance.set_start.return_value = mock_text_instance
        mock_text_instance.close = MagicMock()

        mock_composite_instance = MockCompositeVideoClip.return_value
        mock_composite_instance.set_audio.return_value = mock_composite_instance
        mock_composite_instance.set_duration.return_value = mock_composite_instance
        mock_composite_instance.write_videofile = MagicMock()
        mock_composite_instance.close = MagicMock()

        yield {
            "AudioFileClip": MockAudioFileClip,
            "ImageClip": MockImageClip,
            "TextClip": MockTextClip,
            "CompositeVideoClip": MockCompositeVideoClip,
            "mock_audio_instance": mock_audio_instance, # Expose instances for direct manipulation if needed
            "mock_image_instance": mock_image_instance,
            "mock_text_instance": mock_text_instance,
            "mock_composite_instance": mock_composite_instance
        }

@pytest.fixture
def mock_file_system_for_video():
    with patch('podcast_to_reels.video_composer.os.path.exists') as mock_exists, \
         patch('podcast_to_reels.video_composer.os.makedirs') as mock_makedirs, \
         patch('builtins.open', new_callable=mock_open) as mock_file:

        # Default: audio and image files exist, output dirs might not
        def exists_side_effect(path):
            if path == "dummy_audio.mp3": return True
            if path.startswith("output/images/scene_"): return True # All scene images exist
            if path == "output/video_output": return False # Output video dir
            if path == "output/srt_output": return False # Output SRT dir
            return False # Other paths (like output dirs) don't exist initially
        mock_exists.side_effect = exists_side_effect

        yield {"exists": mock_exists, "makedirs": mock_makedirs, "open": mock_file}


# --- Tests for format_srt_timestamp ---
def test_format_srt_timestamp():
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(1.234) == "00:00:01,234"
    assert format_srt_timestamp(65.05) == "00:01:05,050"
    assert format_srt_timestamp(3661.0) == "01:01:01,000"

# --- Tests for generate_srt_from_transcript ---
SAMPLE_TRANSCRIPT_DATA = {
    "segments": [
        {"text": "Hello world.", "start": 0.1, "end": 1.5},
        {"text": "This is a test.", "start": 2.0, "end": 3.5},
        {"text": "  Another line.  ", "start": 4.0, "end": 5.0}, # Test stripping
        {"text": "", "start": 5.5, "end": 6.0}, # Empty segment, should be skipped
    ]
}
EXPECTED_SRT_CONTENT = """1
00:00:00,100 --> 00:00:01,500
Hello world.

2
00:00:02,000 --> 00:00:03,500
This is a test.

3
00:00:04,000 --> 00:00:05,000
Another line.""" # Note: No trailing newline for the last segment's text in this expected output. Joins with \n.

def test_generate_srt_from_transcript_success(mock_file_system_for_video):
    output_srt_path = "output/srt_output/test.srt"
    success = generate_srt_from_transcript(SAMPLE_TRANSCRIPT_DATA, output_srt_path)

    assert success is True
    mock_file_system_for_video["makedirs"].assert_called_once_with("output/srt_output", exist_ok=True)
    mock_file_system_for_video["open"].assert_called_once_with(output_srt_path, "w", encoding="utf-8")

    # Check content written
    handle = mock_file_system_for_video["open"]()
    written_srt = "".join(call_arg[0] for call_arg in handle.write.call_args_list) # Concatenate all writes
    assert written_srt.strip() == EXPECTED_SRT_CONTENT # Use strip to handle potential final newline


def test_generate_srt_invalid_data():
    assert generate_srt_from_transcript(None, "path.srt") is False
    assert generate_srt_from_transcript({}, "path.srt") is False

def test_generate_srt_io_error(mock_file_system_for_video):
    mock_file_system_for_video["open"].side_effect = IOError("Disk full")
    assert generate_srt_from_transcript(SAMPLE_TRANSCRIPT_DATA, "path.srt") is False

# --- Tests for compose_video ---
SAMPLE_SCENES_DATA = [
    {"start_time": 0.0, "end_time": 3.0, "chunk_text": "Scene 1", "image_prompt": "Prompt 1"},
    {"start_time": 3.0, "end_time": 6.0, "chunk_text": "Scene 2", "image_prompt": "Prompt 2"},
    {"start_time": 6.0, "end_time": 10.0, "chunk_text": "Scene 3", "image_prompt": "Prompt 3"},
]

def test_compose_video_success_no_subtitles(mock_moviepy_clips, mock_file_system_for_video):
    audio_path = "dummy_audio.mp3"
    images_dir = "output/images"
    output_video_path = "output/video_output/final.mp4"

    success = compose_video(audio_path, SAMPLE_SCENES_DATA, images_dir, output_video_path, None)

    assert success is True
    mock_moviepy_clips["AudioFileClip"].assert_called_once_with(audio_path)
    assert mock_moviepy_clips["ImageClip"].call_count == len(SAMPLE_SCENES_DATA)

    # Check that ImageClips were configured correctly (example for first clip)
    first_image_clip_call_args = mock_moviepy_clips["ImageClip"].call_args_list[0]
    assert first_image_clip_call_args[0][0] == os.path.join(images_dir, "scene_0.png")

    # Check that CompositeVideoClip was called with the image clips
    # and that write_videofile was called on its result
    mock_moviepy_clips["CompositeVideoClip"].assert_called_once()
    composite_args = mock_moviepy_clips["CompositeVideoClip"].call_args[0][0] # First arg is list of clips
    assert len(composite_args) == len(SAMPLE_SCENES_DATA) # Only image clips

    final_video_mock = mock_moviepy_clips["mock_composite_instance"]
    final_video_mock.set_audio.assert_called_once_with(mock_moviepy_clips["mock_audio_instance"])
    final_video_mock.write_videofile.assert_called_once()
    write_args = final_video_mock.write_videofile.call_args[0]
    assert write_args[0] == output_video_path

def test_compose_video_audio_file_not_found(mock_file_system_for_video):
    mock_file_system_for_video["exists"].side_effect = lambda path: path != "dummy_audio.mp3"
    success = compose_video("dummy_audio.mp3", SAMPLE_SCENES_DATA, "img_dir", "out.mp4")
    assert success is False

def test_compose_video_image_file_not_found(mock_moviepy_clips, mock_file_system_for_video):
    # Simulate first image missing
    def custom_exists(path):
        if path == "dummy_audio.mp3": return True
        if path == os.path.join("output/images", "scene_0.png"): return False # Scene 0 image missing
        if path.startswith("output/images/scene_"): return True # Other images exist
        return False
    mock_file_system_for_video["exists"].side_effect = custom_exists

    success = compose_video("dummy_audio.mp3", SAMPLE_SCENES_DATA, "output/images", "out.mp4")
    assert success is True # Should still compose with remaining images
    assert mock_moviepy_clips["ImageClip"].call_count == len(SAMPLE_SCENES_DATA) - 1


def test_compose_video_with_original_subtitles(mock_moviepy_clips, mock_file_system_for_video):
    sub_config = {"type": "orig", "original_transcript": SAMPLE_TRANSCRIPT_DATA}
    compose_video("dummy_audio.mp3", SAMPLE_SCENES_DATA, "output/images", "out.mp4", sub_config)

    assert mock_moviepy_clips["TextClip"].call_count == 3 # 3 valid segments in SAMPLE_TRANSCRIPT_DATA
    # Check an example TextClip call
    first_text_call_args = mock_moviepy_clips["TextClip"].call_args_list[0][0] # Args of first call
    assert first_text_call_args[0] == "Hello world." # Text of first segment

    composite_args = mock_moviepy_clips["CompositeVideoClip"].call_args[0][0]
    assert len(composite_args) == len(SAMPLE_SCENES_DATA) + 3 # ImageClips + TextClips

def test_compose_video_with_both_subtitles(mock_moviepy_clips, mock_file_system_for_video):
    translated_transcript = {
        "segments": [
            {"text": "Translated Hello.", "start": 0.1, "end": 1.5},
            {"text": "Translated Test.", "start": 2.0, "end": 3.5},
        ]
    }
    sub_config = {
        "type": "both",
        "original_transcript": SAMPLE_TRANSCRIPT_DATA,
        "translated_transcript": translated_transcript
    }
    compose_video("dummy_audio.mp3", SAMPLE_SCENES_DATA, "output/images", "out.mp4", sub_config)

    # 3 from original, 2 from translated
    assert mock_moviepy_clips["TextClip"].call_count == 3 + 2
    composite_args = mock_moviepy_clips["CompositeVideoClip"].call_args[0][0]
    assert len(composite_args) == len(SAMPLE_SCENES_DATA) + 5

def test_compose_video_no_image_clips_created(mock_moviepy_clips, mock_file_system_for_video):
    # Simulate all images missing
    mock_file_system_for_video["exists"].side_effect = lambda path: path == "dummy_audio.mp3"
    success = compose_video("dummy_audio.mp3", SAMPLE_SCENES_DATA, "output/images", "out.mp4")
    assert success is False # Aborts if no image clips

def test_compose_video_moviepy_exception_on_write(mock_moviepy_clips, mock_file_system_for_video):
    mock_moviepy_clips["mock_composite_instance"].write_videofile.side_effect = Exception("MoviePy write error")
    success = compose_video("dummy_audio.mp3", SAMPLE_SCENES_DATA, "output/images", "out.mp4")
    assert success is False

def test_compose_video_creates_output_directory(mock_moviepy_clips, mock_file_system_for_video):
    output_video_path = "new_vid_dir/final.mp4"
    # Simulate output video directory not existing
    original_exists = mock_file_system_for_video["exists"].side_effect
    def new_exists(path):
        if path == "new_vid_dir": return False
        return original_exists(path)
    mock_file_system_for_video["exists"].side_effect = new_exists

    compose_video("dummy_audio.mp3", SAMPLE_SCENES_DATA, "output/images", output_video_path)
    mock_file_system_for_video["makedirs"].assert_any_call("new_vid_dir", exist_ok=True)

```
