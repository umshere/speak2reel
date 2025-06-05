import argparse
import os
import json
import time
import shutil
from dotenv import load_dotenv

# Project Modules
from podcast_to_reels.downloader import download_audio
from podcast_to_reels.transcriber import transcribe_audio
from podcast_to_reels.translator import translate_text
from podcast_to_reels.scene_splitter import split_transcript_into_scenes
from podcast_to_reels.image_generator import generate_image_from_prompt
from podcast_to_reels.video_composer import compose_video, generate_srt_from_transcript

def main():
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(description="Automated pipeline to create video reels from podcasts/YouTube videos.")
    parser.add_argument("--url", type=str, required=True, help="The YouTube URL of the podcast/video.")
    parser.add_argument("--duration", type=int, default=60, help="Maximum duration of the reel in seconds (default: 60).")
    parser.add_argument("--subtitles", type=str, default="none", choices=["none", "orig", "en", "both"],
                        help="Subtitle preference: 'none', 'orig' (original language), 'en' (English), 'both' (original and English). Default: 'none'.")
    parser.add_argument("--output_dir", type=str, default="output", help="Directory to save all artifacts (default: 'output').")
    parser.add_argument("--fasttext_model_path", type=str, default="lid.176.bin",
                        help="Path to the FastText language detection model (lid.176.bin).")
    parser.add_argument("--skip_image_generation", action="store_true", help="Skip image generation (useful for testing video composition with existing images).")
    parser.add_argument("--skip_video_composition", action="store_true", help="Skip video composition (useful for testing earlier stages).")


    args = parser.parse_args()

    print("Starting Podcast-to-Reels Pipeline...")
    print(f"Arguments: {args}")

    # --- 1. Create Output Directories ---
    base_output_dir = args.output_dir
    audio_output_dir = base_output_dir
    transcripts_output_dir = os.path.join(base_output_dir, "transcripts")
    images_output_dir = os.path.join(base_output_dir, "images")
    video_output_dir = base_output_dir # Main reel saved in base output dir

    os.makedirs(audio_output_dir, exist_ok=True)
    os.makedirs(transcripts_output_dir, exist_ok=True)
    os.makedirs(images_output_dir, exist_ok=True)
    # video_output_dir is created by compose_video if needed

    # Define file paths
    downloaded_audio_path = os.path.join(audio_output_dir, "downloaded_audio.mp3")
    original_transcript_path = os.path.join(transcripts_output_dir, "original_transcript.json")
    english_translation_path = os.path.join(transcripts_output_dir, "english_translation.json")
    final_reel_path = os.path.join(video_output_dir, "final_reel.mp4")

    # --- 2. Download Audio ---
    print(f"\n[Step 1/7] Downloading audio from URL: {args.url} (max duration: {args.duration}s)")
    download_success = download_audio(args.url, downloaded_audio_path, max_duration=args.duration)
    if not download_success or not os.path.exists(downloaded_audio_path):
        print("Error: Audio download failed. Exiting pipeline.")
        return
    print(f"Audio downloaded successfully to {downloaded_audio_path}")

    # --- 3. Transcribe Audio ---
    print(f"\n[Step 2/7] Transcribing audio file: {downloaded_audio_path}")
    # Ensure fasttext model path is handled if it's critical for your transcribe_audio implementation
    # For now, assuming transcribe_audio can find it or has a default if not passed.
    transcribe_success = transcribe_audio(downloaded_audio_path, original_transcript_path, args.fasttext_model_path)
    if not transcribe_success or not os.path.exists(original_transcript_path):
        print("Error: Audio transcription failed. Exiting pipeline.")
        # Clean up downloaded audio if transcription fails
        if os.path.exists(downloaded_audio_path): os.remove(downloaded_audio_path)
        return
    print(f"Audio transcribed successfully. Original transcript saved to {original_transcript_path}")

    with open(original_transcript_path, 'r', encoding='utf-8') as f:
        original_transcript_data = json.load(f)

    detected_language = original_transcript_data.get("language", "unknown")
    print(f"Detected language from original transcript: {detected_language}")

    # --- 4. Translate Transcript (Optional) ---
    translated_transcript_data = None
    if args.subtitles in ["en", "both"] and detected_language != "en":
        print(f"\n[Step 3/7] Translating transcript from '{detected_language}' to English...")
        if not original_transcript_data.get("segments"):
            print("Warning: No segments found in original transcript to translate.")
        else:
            translated_segments = []
            num_segments = len(original_transcript_data["segments"])
            for i, segment in enumerate(original_transcript_data["segments"]):
                text_to_translate = segment.get("text", "")
                if text_to_translate:
                    print(f"  Translating segment {i+1}/{num_segments}...")
                    translated_text = translate_text(text_to_translate, target_language="en", source_language=detected_language)
                    if translated_text:
                        translated_segments.append({**segment, "text": translated_text})
                    else:
                        print(f"Warning: Failed to translate segment {i+1}. Using original text.")
                        translated_segments.append(segment) # Keep original if translation fails
                    time.sleep(0.2) # Small delay to avoid hitting API limits too hard if any (OpenAI usually robust)
                else:
                    translated_segments.append(segment) # Keep empty segment as is

            translated_transcript_data = {
                "language": "en", # Target language
                "segments": translated_segments,
                "text": " ".join(s.get("text","") for s in translated_segments) # Reconstruct full text
            }
            with open(english_translation_path, 'w', encoding='utf-8') as f:
                json.dump(translated_transcript_data, f, ensure_ascii=False, indent=4)
            print(f"Transcript translated to English. Saved to {english_translation_path}")
    elif args.subtitles in ["en", "both"] and detected_language == "en":
        print("\n[Step 3/7] Original transcript is already in English. Skipping translation.")
        # Use original as "translated" for subtitle logic if needed
        translated_transcript_data = original_transcript_data
        # Optionally copy to english_translation.json for consistency if downstream steps expect it
        shutil.copy(original_transcript_path, english_translation_path)
        print(f"Copied original English transcript to {english_translation_path} for consistency.")

    else:
        print("\n[Step 3/7] Translation not required based on subtitle settings or detected language.")

    # --- 5. Split Scenes & Generate Prompts ---
    # Use original transcript for scene splitting, as visual cues should match original audio context.
    print(f"\n[Step 4/7] Splitting transcript into scenes and generating image prompts...")
    scenes_data = split_transcript_into_scenes(original_transcript_data) # Default words_per_chunk is 20
    if not scenes_data:
        print("Error: Failed to split transcript into scenes. Exiting pipeline.")
        return
    print(f"Successfully split into {len(scenes_data)} scenes with image prompts.")
    # For debugging, can save scenes_data
    with open(os.path.join(transcripts_output_dir, "scenes_with_prompts.json"), 'w', encoding='utf-8') as f:
        json.dump(scenes_data, f, ensure_ascii=False, indent=4)


    # --- 6. Generate Images ---
    if args.skip_image_generation:
        print("\n[Step 5/7] Skipping image generation as per --skip_image_generation flag.")
        # Check if images exist from a previous run if skipping
        all_images_exist = True
        if not scenes_data: # Should not happen if previous step succeeded
             all_images_exist = False
        else:
            for i in range(len(scenes_data)):
                expected_image_path = os.path.join(images_output_dir, f"scene_{i}.png")
                if not os.path.exists(expected_image_path):
                    print(f"Warning: Image {expected_image_path} not found for skipped generation.")
                    all_images_exist = False
                    break
        if not all_images_exist and not args.skip_video_composition:
             print("Error: Skipping image generation, but not all required images found. Video composition might fail or be incorrect.")
             # Decide if to exit or let it try and fail
    else:
        print(f"\n[Step 5/7] Generating images for {len(scenes_data)} scenes...")
        generated_image_count = 0
        for i, scene in enumerate(scenes_data):
            image_prompt = scene.get("image_prompt")
            if not image_prompt:
                print(f"Warning: Scene {i} has no image prompt. Skipping image generation for this scene.")
                # Create a placeholder or copy a default image if you want the video to still have a visual
                # For now, video composer will skip if image not found.
                continue

            print(f"  Generating image for scene {i+1}/{len(scenes_data)}: Prompt: '{image_prompt[:50]}...'")
            success = generate_image_from_prompt(image_prompt, images_output_dir, scene_index=i)
            if success:
                generated_image_count += 1
                print(f"    Image for scene {i} generated successfully.")
            else:
                print(f"Warning: Failed to generate image for scene {i}.")
                # Continue to next image, video composer will handle missing images if necessary

            if i < len(scenes_data) - 1: # Avoid delay after the last image
                print(f"    Waiting 1 second before next image generation (rate limiting)...")
                time.sleep(1)

        if generated_image_count == 0 and scenes_data:
            print("Error: No images were generated successfully. Exiting pipeline before video composition.")
            return
        print(f"Image generation complete. {generated_image_count}/{len(scenes_data)} images generated.")


    # --- 7. Compose Video ---
    if args.skip_video_composition:
        print("\n[Step 6/7] Skipping video composition as per --skip_video_composition flag.")
    else:
        print(f"\n[Step 6/7] Composing video...")
        sub_config = {"type": args.subtitles}
        if args.subtitles == "orig":
            sub_config["original_transcript"] = original_transcript_data
        elif args.subtitles == "en":
            # translated_transcript_data will be original if already English, or the translation
            sub_config["translated_transcript"] = translated_transcript_data if translated_transcript_data else original_transcript_data
        elif args.subtitles == "both":
            sub_config["original_transcript"] = original_transcript_data # This should be the actual original lang
            sub_config["translated_transcript"] = translated_transcript_data # This is the English one
            # If original was English, translated_transcript_data points to original_transcript_data
            # Adjust if original_transcript_data is English and "both" is chosen
            if detected_language == "en":
                 # For "both" with original English, maybe only show English or duplicate for demo?
                 # Current logic would show English text twice if original was English and translated_transcript_data points to it.
                 # Let's refine: if original is English, 'both' behaves like 'orig' or 'en'.
                 print("Warning: Subtitle type 'both' selected but original language is English. Will only display English subtitles.")
                 sub_config["type"] = "en" # Or "orig", effectively the same here
                 sub_config["translated_transcript"] = original_transcript_data
                 del sub_config["original_transcript"]


        video_success = compose_video(
            audio_path=downloaded_audio_path,
            scenes_data=scenes_data,
            images_dir=images_output_dir,
            output_video_path=final_reel_path,
            subtitles_config=sub_config
        )
        if not video_success:
            print("Error: Video composition failed.")
            # Consider cleanup of intermediate files
            return
        print(f"Video composed successfully: {final_reel_path}")

    # --- 8. Generate SRT Files (Optional) ---
    print(f"\n[Step 7/7] Generating SRT subtitle files (if applicable)...")
    srt_generated_paths = []
    if args.subtitles == "orig":
        srt_path = os.path.join(transcripts_output_dir, "reel_orig.srt")
        if generate_srt_from_transcript(original_transcript_data, srt_path):
            srt_generated_paths.append(srt_path)
    elif args.subtitles == "en":
        transcript_for_srt = translated_transcript_data if translated_transcript_data else (original_transcript_data if detected_language == "en" else None)
        if transcript_for_srt:
            srt_path = os.path.join(transcripts_output_dir, "reel_en.srt")
            if generate_srt_from_transcript(transcript_for_srt, srt_path):
                srt_generated_paths.append(srt_path)
        else:
            print("Warning: No English transcript available to generate English SRT file.")
    elif args.subtitles == "both":
        # SRT for original language
        srt_path_orig = os.path.join(transcripts_output_dir, "reel_orig.srt")
        if generate_srt_from_transcript(original_transcript_data, srt_path_orig):
            srt_generated_paths.append(srt_path_orig)

        # SRT for English translation
        transcript_for_en_srt = translated_transcript_data if translated_transcript_data else (original_transcript_data if detected_language == "en" else None)
        if transcript_for_en_srt:
            srt_path_en = os.path.join(transcripts_output_dir, "reel_en.srt")
            if generate_srt_from_transcript(transcript_for_en_srt, srt_path_en):
                srt_generated_paths.append(srt_path_en)
        else:
            print("Warning: No English transcript available to generate English SRT file for 'both' option.")

    if srt_generated_paths:
        print(f"SRT files generated: {', '.join(srt_generated_paths)}")
    else:
        print("No SRT files were generated based on subtitle settings.")

    print("\nPodcast-to-Reels Pipeline finished successfully!")
    print(f"All outputs are in the directory: {args.output_dir}")
    # Consider cleanup of intermediate files if needed, e.g. downloaded_audio.mp3 if not wanted.
    # For now, all artifacts are kept.

if __name__ == "__main__":
    main()
```
