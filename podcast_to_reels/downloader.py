import yt_dlp
import os

def download_audio(url: str, output_path: str = "audio.mp3", max_duration: int = 600):
    """
    Downloads audio from a given URL, saves it as MP3, and trims if necessary.

    Args:
        url: The URL of the video/audio to download.
        output_path: The path to save the downloaded audio file.
                     The directory for the output_path will be created if it doesn't exist.
        max_duration: The maximum duration of the audio in seconds.
                      If the downloaded audio is longer, it will be trimmed.

    Returns:
        str: The final path of the downloaded and processed audio file, or None if an error occurred.
    """
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Ensure the filename has an .mp3 extension
    filename, _ = os.path.splitext(os.path.basename(output_path))
    # yt-dlp adds the extension automatically, so we pass the path without it
    # but will rename the file later if necessary to match the exact output_path.
    temp_output_template = os.path.join(output_dir, f"{filename}.%(ext)s")


    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': temp_output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'postprocessor_args': [
            '-ss', '0', # Start from the beginning
            '-to', str(max_duration), # Trim to max_duration
        ],
        'noplaylist': True, # Download only single video if URL is a playlist
        'quiet': True, # Suppress output
        'no_warnings': True, # Suppress warnings
    }

    actual_output_path_mp3 = os.path.join(output_dir, f"{filename}.mp3")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download([url])
            if error_code != 0:
                print(f"Error during download: yt-dlp exited with code {error_code}")
                return None

        # yt-dlp should have created an mp3 file based on the template
        # We need to find it, in case the original extension was different (e.g. webm)
        # For example, if temp_output_template was "audio.%(ext)s" and a webm was downloaded,
        # yt-dlp creates "audio.webm" then converts to "audio.mp3".

        # Check if the expected mp3 file exists
        if not os.path.exists(actual_output_path_mp3):
            # Fallback: try to find any .mp3 file in the output directory that starts with the filename
            # This is a bit of a guess if the naming is not exactly as expected.
            found_mp3 = None
            for f in os.listdir(output_dir):
                if f.startswith(filename) and f.endswith(".mp3"):
                    found_mp3 = os.path.join(output_dir, f)
                    break
            if found_mp3:
                 # If a matching mp3 is found but not with the exact output_path name, rename it.
                if found_mp3 != actual_output_path_mp3:
                    os.rename(found_mp3, actual_output_path_mp3)
            else:
                print(f"Error: Expected MP3 file not found at {actual_output_path_mp3} after download and conversion.")
                # Attempt to list files to help debug
                print(f"Files in {output_dir}: {os.listdir(output_dir)}")
                return None

        # Ensure the final file is at the specified output_path
        if actual_output_path_mp3 != output_path:
            # This can happen if output_path had a different (or no) extension.
            if os.path.exists(output_path) and not os.path.samefile(actual_output_path_mp3, output_path):
                os.remove(output_path) # Remove if it's a different file to avoid error on rename
            elif os.path.exists(output_path) and os.path.samefile(actual_output_path_mp3, output_path):
                # It's already the same file, do nothing
                pass
            else: # actual_output_path_mp3 exists, output_path does not or is different
                 os.rename(actual_output_path_mp3, output_path)

        return output_path

    except yt_dlp.utils.DownloadError as e:
        print(f"An error occurred during download: {e}")
        # Clean up partially downloaded file if it exists and is named as expected
        if os.path.exists(actual_output_path_mp3):
            os.remove(actual_output_path_mp3)
        # Also check if the original output_path (if different) exists
        if output_path != actual_output_path_mp3 and os.path.exists(output_path):
            os.remove(output_path)
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # Clean up
        if os.path.exists(actual_output_path_mp3):
            os.remove(actual_output_path_mp3)
        if output_path != actual_output_path_mp3 and os.path.exists(output_path):
            os.remove(output_path)
        return None
