import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
from podcast_to_reels.downloader import download_audio

@pytest.fixture
def mock_yt_dlp():
    with patch('podcast_to_reels.downloader.yt_dlp.YoutubeDL') as mock_youtubedl:
        instance = mock_youtubedl.return_value.__enter__.return_value
        instance.download.return_value = 0 # Success
        # Simulate that yt-dlp creates a file with a .mp3 extension
        # This effect is indirect; we'll check for os.rename/os.path.exists
        yield instance

@pytest.fixture
def mock_os_utils():
    with patch('podcast_to_reels.downloader.os.path.exists') as mock_exists, \
         patch('podcast_to_reels.downloader.os.makedirs') as mock_makedirs, \
         patch('podcast_to_reels.downloader.os.path.splitext') as mock_splitext, \
         patch('podcast_to_reels.downloader.os.path.basename') as mock_basename, \
         patch('podcast_to_reels.downloader.os.path.join', side_effect=os.path.join) as mock_join, \
         patch('podcast_to_reels.downloader.os.rename') as mock_rename, \
         patch('podcast_to_reels.downloader.os.remove') as mock_remove, \
         patch('podcast_to_reels.downloader.os.listdir') as mock_listdir:

        mock_splitext.return_value = ('test_audio', '.mp3') # Default split
        mock_basename.side_effect = os.path.basename # Use actual basename

        # Default side effect for exists:
        # True for output dir (simulating it's created or already there)
        # True for the expected final mp3 after download (simulating yt-dlp success)
        # False for other checks unless specifically overridden in a test
        def exists_side_effect(path):
            if path == "output/audio": # directory for output_path
                return True
            if path == "output/audio/test_audio.mp3": # final expected mp3
                 return True
            if path.endswith(".webm.mp3"): # if temp name was .webm.mp3
                return True # simulate it exists before rename
            return False
        mock_exists.side_effect = exists_side_effect
        mock_listdir.return_value = ["test_audio.mp3"]


        yield {
            "exists": mock_exists, "makedirs": mock_makedirs,
            "splitext": mock_splitext, "basename": mock_basename,
            "join": mock_join, "rename": mock_rename, "remove": mock_remove,
            "listdir": mock_listdir
        }

def test_download_audio_success_default_path(mock_yt_dlp, mock_os_utils):
    """Test successful audio download with default output path and duration."""
    url = "https://www.youtube.com/watch?v=test"

    # Ensure the final output_path (default "audio.mp3") is recognized as existing post-download
    def exists_side_effect_default(path):
        if path == "": # Dirname of "audio.mp3"
            return True
        if path == "audio.mp3": # default output name
            return True
        return False
    mock_os_utils["exists"].side_effect = exists_side_effect_default
    mock_os_utils["splitext"].return_value = ('audio', '.mp3')
    mock_os_utils["listdir"].return_value = ["audio.mp3"]


    result_path = download_audio(url)

    assert result_path == "audio.mp3"
    mock_yt_dlp.download.assert_called_once_with([url])

    # Check ydl_opts passed to YoutubeDL
    args, _ = mock_yt_dlp.params_builder_list[0] # YoutubeDL called with new(ydl_opts)
    ydl_opts = args[0] # The first arg is the ydl_opts dict

    assert ydl_opts['postprocessors'][0]['key'] == 'FFmpegExtractAudio'
    assert ydl_opts['postprocessors'][0]['preferredcodec'] == 'mp3'
    assert ydl_opts['postprocessor_args'] == ['-ss', '0', '-to', '600'] # Default max_duration
    assert ydl_opts['outtmpl'] == os.path.join("", "audio.%(ext)s")


def test_download_audio_success_custom_path_and_duration(mock_yt_dlp, mock_os_utils):
    """Test successful audio download with custom path and duration."""
    url = "https://www.youtube.com/watch?v=test"
    output_path = "output/audio/custom_audio.mp3"
    max_duration = 300

    mock_os_utils["splitext"].return_value = ('custom_audio', '.mp3')
    def custom_exists(path):
        if path == "output/audio": return True
        if path == output_path: return True
        return False
    mock_os_utils["exists"].side_effect = custom_exists
    mock_os_utils["listdir"].return_value = ["custom_audio.mp3"]


    result_path = download_audio(url, output_path, max_duration)

    assert result_path == output_path
    mock_yt_dlp.download.assert_called_once_with([url])
    mock_os_utils["makedirs"].assert_called_with("output/audio", exist_ok=True)

    args, _ = mock_yt_dlp.params_builder_list[0]
    ydl_opts = args[0]
    assert ydl_opts['postprocessor_args'] == ['-ss', '0', '-to', str(max_duration)]
    assert ydl_opts['outtmpl'] == os.path.join("output/audio", "custom_audio.%(ext)s")


def test_download_audio_yt_dlp_download_error(mock_yt_dlp, mock_os_utils):
    """Test handling of yt-dlp download error."""
    mock_yt_dlp.download.return_value = 1 # Simulate error code
    url = "https://www.youtube.com/watch?v=test_error"

    result_path = download_audio(url)

    assert result_path is None
    mock_yt_dlp.download.assert_called_once_with([url])


@patch('podcast_to_reels.downloader.yt_dlp.utils.DownloadError', Exception) # Mock specific exception
def test_download_audio_yt_dlp_exception(mock_yt_dlp, mock_os_utils):
    """Test handling of yt-dlp DownloadError exception."""
    mock_yt_dlp.download.side_effect = yt_dlp.utils.DownloadError("Simulated download error")
    url = "https://www.youtube.com/watch?v=test_exception"
    output_path = "output/audio/exception_test.mp3"

    # Simulate that the file might exist before attempting removal in except block
    mock_os_utils["exists"].side_effect = lambda p: p == output_path or p == "output/audio"

    result_path = download_audio(url, output_path=output_path)

    assert result_path is None
    mock_os_utils["remove"].assert_any_call(os.path.join("output/audio", "exception_test.mp3"))


def test_download_audio_output_directory_creation(mock_yt_dlp, mock_os_utils):
    """Test that output directory is created if it doesn't exist."""
    url = "https://www.youtube.com/watch?v=test_dir"
    output_path = "new_dir/audio.mp3"

    mock_os_utils["exists"].side_effect = lambda p: p == output_path # only final file exists after download
    mock_os_utils["splitext"].return_value = ('audio', '.mp3')
    mock_os_utils["listdir"].return_value = ["audio.mp3"]


    download_audio(url, output_path)

    mock_os_utils["makedirs"].assert_called_once_with("new_dir", exist_ok=True)

def test_download_audio_renaming_logic(mock_yt_dlp, mock_os_utils):
    """Test renaming logic if yt-dlp saves with a different extension initially."""
    url = "https://www.youtube.com/watch?v=test_rename"
    output_path = "output/audio/final_name.mp3" # User wants this
    # Simulate yt-dlp outputting a .webm first, then converting to .mp3 but with a generic name
    # based on outtmpl pattern before postprocessing rename (which yt-dlp should do)
    # Our code primarily relies on yt-dlp naming it correctly via preferredcodec.
    # This test checks if our fallback (listdir) and renaming to output_path works.

    temp_file_from_ydl = "output/audio/temp_name.mp3" # What if yt-dlp made this

    mock_os_utils["splitext"].return_value = ('final_name', '.mp3') # For the target output_path

    def exists_side_effect(path):
        if path == "output/audio": return True
        if path == temp_file_from_ydl: return True # File found by listdir
        # The final_name.mp3 does NOT exist initially, triggering rename
        if path == output_path: return False
        return False
    mock_os_utils["exists"].side_effect = exists_side_effect

    # listdir finds the file yt-dlp actually created
    mock_os_utils["listdir"].return_value = [os.path.basename(temp_file_from_ydl)]

    result = download_audio(url, output_path)

    assert result == output_path
    # Check that rename was called from temp_file_from_ydl to output_path
    mock_os_utils["rename"].assert_called_once_with(temp_file_from_ydl, output_path)


def test_download_audio_no_mp3_found_after_download(mock_yt_dlp, mock_os_utils):
    """Test scenario where the expected MP3 file is not found after download."""
    url = "https://www.youtube.com/watch?v=test_no_mp3"
    output_path = "output/audio/no_such_file.mp3"

    mock_os_utils["splitext"].return_value = ('no_such_file', '.mp3')

    # Simulate that the target MP3 and any variation never gets created
    mock_os_utils["exists"].side_effect = lambda p: p == "output/audio" # Only dir exists
    mock_os_utils["listdir"].return_value = ["some_other_file.txt"] # No MP3s

    result = download_audio(url, output_path)
    assert result is None

def test_download_audio_unexpected_exception(mock_yt_dlp, mock_os_utils):
    """Test handling of a generic unexpected exception during the process."""
    mock_yt_dlp.download.side_effect = Exception("Highly unexpected error")
    url = "https://www.youtube.com/watch?v=test_super_error"
    output_path = "output/audio/super_error.mp3"

    mock_os_utils["exists"].side_effect = lambda p: p == output_path or p == "output/audio"

    result = download_audio(url, output_path)

    assert result is None
    mock_os_utils["remove"].assert_any_call(os.path.join("output/audio", "super_error.mp3"))
```
