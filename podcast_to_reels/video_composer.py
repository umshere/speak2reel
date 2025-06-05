import os
from moviepy.editor import (
    AudioFileClip, ImageClip, CompositeVideoClip, TextClip,
    concatenate_videoclips
)
from moviepy.config import change_settings

# If ImageMagick is not found by MoviePy, you might need to set its path.
# This is often an issue on Windows or if ImageMagick is installed in a non-standard location.
# Example: change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"})
# For this project, we assume ImageMagick is installed and discoverable or not strictly needed for TextClip rasterization
# if a default font that doesn't rely heavily on it is used, or if MoviePy's internal text rendering is sufficient.

def format_srt_timestamp(seconds: float) -> str:
    """Converts seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    millis = int((seconds - int(seconds)) * 1000)
    seconds = int(seconds)
    minutes = seconds // 60
    seconds %= 60
    hours = minutes // 60
    minutes %= 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

def generate_srt_from_transcript(transcript_data: dict, output_srt_path: str):
    """
    Generates an SRT subtitle file from Whisper's verbose JSON transcript data.

    Args:
        transcript_data: A dictionary containing a 'segments' key, where segments
                         is a list of dicts, each with 'text', 'start', and 'end'.
        output_srt_path: Path to save the generated .srt file.

    Returns:
        bool: True if SRT generation was successful, False otherwise.
    """
    if not transcript_data or "segments" not in transcript_data:
        print("Error: Invalid transcript data provided for SRT generation.")
        return False

    segments = transcript_data["segments"]
    srt_content = []

    for i, segment in enumerate(segments):
        text = segment.get("text", "").strip()
        start_time = segment.get("start", 0.0)
        end_time = segment.get("end", 0.0)

        if not text: # Skip empty segments
            continue

        srt_content.append(str(i + 1))
        srt_content.append(f"{format_srt_timestamp(start_time)} --> {format_srt_timestamp(end_time)}")
        srt_content.append(text)
        srt_content.append("")  # Blank line separator

    try:
        output_dir = os.path.dirname(output_srt_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_content))
        print(f"SRT file generated successfully at {output_srt_path}")
        return True
    except IOError as e:
        print(f"Error writing SRT file to {output_srt_path}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during SRT generation: {e}")
    return False


def compose_video(
    audio_path: str,
    scenes_data: list,
    images_dir: str,
    output_video_path: str,
    subtitles_config: dict = None
) -> bool:
    """
    Composes a video from an audio file, scene images, and optional subtitles.

    Args:
        audio_path: Path to the original (or trimmed) audio file.
        scenes_data: List of scene dictionaries from SceneSplitter. Each dict contains
                     'start_time', 'end_time', 'chunk_text', 'image_prompt'.
        images_dir: Directory containing generated images (e.g., scene_0.png).
        output_video_path: Path to save the final MP4 video.
        subtitles_config: Optional dictionary for subtitle configuration:
            {
                "type": "none" | "orig" | "en" | "both",
                "original_transcript": dict, // Whisper verbose JSON
                "translated_transcript": dict // Whisper verbose JSON (text translated)
            }

    Returns:
        True if video composition is successful, False otherwise.
    """
    target_resolution = (1080, 1920) # Vertical 9:16
    fps = 30

    try:
        # 1. Load audio
        if not os.path.exists(audio_path):
            print(f"Error: Audio file not found at {audio_path}")
            return False
        main_audio_clip = AudioFileClip(audio_path)
        video_duration = main_audio_clip.duration

        # 2. Create video clips from images
        image_clips = []
        for i, scene in enumerate(scenes_data):
            image_filename = f"scene_{i}.png"
            image_path = os.path.join(images_dir, image_filename)

            if not os.path.exists(image_path):
                print(f"Warning: Image {image_path} for scene {i} not found. Skipping scene.")
                # Optionally, create a blank clip or use a placeholder
                continue

            scene_duration = scene['end_time'] - scene['start_time']
            if scene_duration <= 0:
                print(f"Warning: Scene {i} has non-positive duration ({scene_duration}s). Skipping.")
                continue

            img_clip = (ImageClip(image_path)
                        .set_duration(scene_duration)
                        .set_start(scene['start_time']))

            # Resize and crop if necessary
            # Option 1: Resize to fit width, then crop height (common for 9:16 from landscape/square)
            # Option 2: Resize to fit height, then crop width
            # Option 3: Resize then pad (less ideal for full-screen reels)
            # Using resize with height and then cropping width, or forcing aspect and cropping

            # Resize to target height, keeping aspect ratio, then crop width if needed
            img_clip = img_clip.resize(height=target_resolution[1])
            if img_clip.w > target_resolution[0]:
                img_clip = img_clip.crop(x_center=img_clip.w/2, width=target_resolution[0])
            # If after resizing height, width is less than target (e.g. portrait image narrower than 9:16)
            # then resize to width and crop height. This handles various aspect ratios.
            elif img_clip.w < target_resolution[0]:
                 img_clip = img_clip.resize(width=target_resolution[0]) # now width is target, height might be > target
                 if img_clip.h > target_resolution[1]:
                     img_clip = img_clip.crop(y_center=img_clip.h/2, height=target_resolution[1])

            # Ensure final size if any dimension is still off (e.g. due to rounding)
            if img_clip.size != list(target_resolution):
                 img_clip = img_clip.resize(target_resolution)


            image_clips.append(img_clip)

        if not image_clips:
            print("Error: No image clips could be created. Aborting video composition.")
            return False

        # 3. Concatenate ImageClips - This is not how MoviePy typically handles clips based on start times.
        # Instead, use CompositeVideoClip with clips that have set_start() and set_duration().
        # video_track = concatenate_videoclips(image_clips, method="compose") # method="compose" might not be ideal for gaps
        # The image_clips already have start_time and duration. CompositeVideoClip is better.
        # Ensure clips are sorted by start time for safety, though they should be.
        image_clips.sort(key=lambda clip: clip.start)

        # Create a base video of the correct duration, can be black or first frame.
        # Using a black background matching total duration to place clips on.
        # Max duration should be from the audio or the end of the last scene.
        final_duration = max(video_duration, max(c.end for c in image_clips) if image_clips else 0)

        # Create a list of all clips to be composited, starting with image clips
        all_video_clips = image_clips


        # 5. Subtitles
        if subtitles_config and subtitles_config.get("type") != "none":
            sub_type = subtitles_config.get("type")
            original_transcript = subtitles_config.get("original_transcript")
            translated_transcript = subtitles_config.get("translated_transcript")

            subtitle_clips = []

            def create_subtitle_textclips(transcript, y_pos, color='white', stroke_color='black', fontsize=40, font='Arial-Bold'):
                clips = []
                if not transcript or "segments" not in transcript:
                    return []
                for segment in transcript["segments"]:
                    text = segment.get("text", "").strip()
                    start = segment.get("start")
                    end = segment.get("end")
                    if not text or start is None or end is None:
                        continue
                    duration = end - start
                    if duration <= 0:
                        continue

                    # Basic wrapping (MoviePy's TextClip can auto-wrap if width is given)
                    # For better wrapping, one might need to manually split lines.
                    txt_clip = (TextClip(text, fontsize=fontsize, font=font, color=color,
                                        stroke_color=stroke_color, stroke_width=1.5,
                                        size=(target_resolution[0]*0.9, None), method='caption') # width=90% of screen
                               .set_position(('center', y_pos))
                               .set_duration(duration)
                               .set_start(start))
                    clips.append(txt_clip)
                return clips

            if sub_type == "orig" and original_transcript:
                subtitle_clips.extend(create_subtitle_textclips(original_transcript, target_resolution[1] * 0.8))
            elif sub_type == "en" and translated_transcript:
                subtitle_clips.extend(create_subtitle_textclips(translated_transcript, target_resolution[1] * 0.8))
            elif sub_type == "both":
                if original_transcript:
                    subtitle_clips.extend(create_subtitle_textclips(original_transcript, target_resolution[1] * 0.75, color='yellow')) # Orig subs higher
                if translated_transcript: # English subs lower
                    subtitle_clips.extend(create_subtitle_textclips(translated_transcript, target_resolution[1] * 0.85, color='white'))

            all_video_clips.extend(subtitle_clips)

        # 4. Create Composite Video Clip and set audio
        # The first element in CompositeVideoClip list is the base layer.
        # If image_clips don't cover the whole duration, need a base canvas.
        # Let's ensure there's a base black clip for the full duration if image clips are sparse.
        # However, if image_clips are meant to be consecutive and fill time, this is different.
        # The current setup implies scenes might not be back-to-back from 0 to video_duration.
        # The provided scene_data implies specific start/end times for images.

        # If using concatenation:
        # video_track = concatenate_videoclips(image_clips).set_duration(final_duration)
        # final_video = video_track.set_audio(main_audio_clip)
        # if subtitle_clips: # If we have subtitles, overlay them on the concatenated track
        #    final_video = CompositeVideoClip([final_video] + subtitle_clips, size=target_resolution)

        # If using CompositeVideoClip for everything (more flexible for gaps):
        final_video = CompositeVideoClip(all_video_clips, size=target_resolution).set_duration(final_duration)
        final_video = final_video.set_audio(main_audio_clip)


        # 6. Write video
        output_dir = os.path.dirname(output_video_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        final_video.write_videofile(
            output_video_path,
            codec="libx264",
            audio_codec="aac",
            fps=fps,
            temp_audiofile_path=os.path.join(output_dir or ".", "temp_audio.m4a"), # For managing temp audio file
            remove_temp=True
        )
        print(f"Video composed successfully at {output_video_path}")
        return True

    except Exception as e:
        # Log the full traceback for debugging
        import traceback
        print(f"An error occurred during video composition: {e}")
        print(traceback.format_exc())
        return False
    finally:
        # Clean up MoviePy resources if necessary (though it's usually good at this)
        if 'main_audio_clip' in locals() and main_audio_clip: main_audio_clip.close()
        for clip_list_name in ['image_clips', 'all_video_clips', 'subtitle_clips']:
            if clip_list_name in locals():
                for clip in locals()[clip_list_name]:
                    if hasattr(clip, 'close') and callable(clip.close):
                        clip.close()
        if 'final_video' in locals() and final_video: final_video.close()


if __name__ == '__main__':
    # Example Usage (requires dummy files and MoviePy with dependencies like FFmpeg)
    # Create dummy files and directories for testing

    print("Setting up dummy files for VideoComposer example...")
    if not os.path.exists("output/video_composer_test"):
        os.makedirs("output/video_composer_test/images", exist_ok=True)

    # Dummy audio (e.g., a silent 10s audio)
    # Trying to create a real silent audio with moviepy for robustness
    from moviepy.editor import AudioArrayClip
    import numpy as np
    dummy_audio_path = "output/video_composer_test/dummy_audio.mp3"
    duration = 10 # seconds
    fps_audio = 44100
    silence = np.zeros((int(duration * fps_audio), 2)) # 2 channels for stereo
    try:
        AudioArrayClip(silence, fps=fps_audio).write_audiofile(dummy_audio_path, codec='mp3')
        print(f"Dummy audio created at {dummy_audio_path}")
    except Exception as e:
        print(f"Could not create dummy audio using MoviePy (FFmpeg needed): {e}")
        print("Falling back to empty file (composition will likely fail).")
        with open(dummy_audio_path, "w") as f: f.write("")


    # Dummy images (e.g., create simple color images if possible, or just empty files)
    # For this test, actual image content isn't crucial, but paths must exist.
    # Creating tiny placeholder PNGs (might need Pillow for this part of example)
    try:
        from PIL import Image
        for i in range(3):
            img_path = f"output/video_composer_test/images/scene_{i}.png"
            if not os.path.exists(img_path):
                img = Image.new('RGB', (300, 300), color = ('red' if i % 2 == 0 else 'blue'))
                img.save(img_path)
        print("Dummy images created.")
    except ImportError:
        print("Pillow not installed. Cannot create dummy PNG images for test. Please create them manually.")
        print("Or ensure images exist at 'output/video_composer_test/images/scene_X.png'")
    except Exception as e:
        print(f"Error creating dummy images: {e}")


    sample_scenes_data = [
        {"start_time": 0.0, "end_time": 3.0, "chunk_text": "Scene 1 text here.", "image_prompt": "Prompt 1"},
        {"start_time": 3.0, "end_time": 6.5, "chunk_text": "Scene 2 with more words.", "image_prompt": "Prompt 2"},
        {"start_time": 6.5, "end_time": 10.0, "chunk_text": "Final scene of this short clip.", "image_prompt": "Prompt 3"},
    ]

    # Dummy transcript data for SRT and subtitles
    sample_transcript = {
        "language": "en",
        "segments": [
            {"text": "Hello this is the first line.", "start": 0.5, "end": 2.8},
            {"text": "And now for a second line of dialogue.", "start": 3.1, "end": 6.2},
            {"text": "The final words are spoken here.", "start": 6.6, "end": 9.5}
        ]
    }

    sample_translated_transcript_es = { # Example if original was Spanish, translated to English
        "language": "es", # This would be the original language
        "segments": [ # Text here is in Spanish for this example
            {"text": "Hola, esta es la primera línea.", "start": 0.5, "end": 2.8},
            {"text": "Y ahora una segunda línea de diálogo.", "start": 3.1, "end": 6.2},
            {"text": "Las palabras finales se dicen aquí.", "start": 6.6, "end": 9.5}
        ]
    }


    # Test SRT generation
    srt_output_path = "output/video_composer_test/subtitles.srt"
    print(f"\nTesting SRT generation to {srt_output_path}...")
    generate_srt_from_transcript(sample_transcript, srt_output_path)

    # Test video composition
    output_video_path = "output/video_composer_test/reel.mp4"
    print(f"\nTesting video composition to {output_video_path} (no subtitles)...")

    # Check if FFmpeg is available by trying to run compose_video
    # This is a very basic check; a more robust check would involve trying a small FFmpeg command.
    try:
        # Attempt a very simple video operation to see if FFmpeg is missing early
        from moviepy.video.fx.all import blackwhite
        ImageClip(np.zeros((100,100,3), dtype=np.uint8), ismask=False).fx(blackwhite).close() # Test a simple fx
        ffmpeg_present = True
    except Exception as e:
        if "FFMPEG_BINARY" in str(e) or "No such file or directory" in str(e).lower() or "Program FFMPEG not found" in str(e):
            print("WARNING: FFmpeg might not be installed or found by MoviePy. Video composition will likely fail.")
            ffmpeg_present = False
        else: # Some other error during this test
            print(f"Pre-check for FFmpeg encountered an error: {e}")
            ffmpeg_present = True # Assume present and let compose_video fail if it's an issue

    if not os.path.exists(dummy_audio_path) or os.path.getsize(dummy_audio_path) == 0:
        print("Dummy audio file is missing or empty. Video composition test will likely fail or be incorrect.")
        ffmpeg_present = False # Cannot proceed if audio is not usable

    if ffmpeg_present:
        success_no_subs = compose_video(
            dummy_audio_path,
            sample_scenes_data,
            "output/video_composer_test/images",
            output_video_path
        )
        print(f"Video composition (no subtitles) success: {success_no_subs}")

        # Test with subtitles
        output_video_with_subs_path = "output/video_composer_test/reel_with_subs.mp4"
        print(f"\nTesting video composition to {output_video_with_subs_path} (original subtitles)...")
        sub_config_orig = {
            "type": "orig",
            "original_transcript": sample_transcript
        }
        success_orig_subs = compose_video(
            dummy_audio_path,
            sample_scenes_data,
            "output/video_composer_test/images",
            output_video_with_subs_path,
            subtitles_config=sub_config_orig
        )
        print(f"Video composition (original subtitles) success: {success_orig_subs}")

        output_video_with_both_subs_path = "output/video_composer_test/reel_with_both_subs.mp4"
        print(f"\nTesting video composition to {output_video_with_both_subs_path} (both subtitles)...")
        # For "both", original_transcript would be the non-English one, translated_transcript the English one.
        # Let's use sample_translated_transcript_es as original and sample_transcript as its "English translation"
        sub_config_both = {
            "type": "both",
            "original_transcript": sample_translated_transcript_es, # Non-English (Spanish)
            "translated_transcript": sample_transcript # English
        }
        success_both_subs = compose_video(
            dummy_audio_path,
            sample_scenes_data,
            "output/video_composer_test/images",
            output_video_with_both_subs_path,
            subtitles_config=sub_config_both
        )
        print(f"Video composition (both subtitles) success: {success_both_subs}")
    else:
        print("Skipping video composition tests as FFmpeg seems to be missing or dummy audio creation failed.")

```
