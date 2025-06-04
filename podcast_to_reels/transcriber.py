import openai
import json
import os
import fasttext
from langdetect import detect, lang_detect_exception
from langdetect.detector_factory import init_factory # For consistent results

# Initialize langdetect factory for consistent results
init_factory()

# Ensure OPENAI_API_KEY is set in environment variables
# For example, by loading from a .env file or setting it directly
# from dotenv import load_dotenv
# load_dotenv()
# if not os.getenv("OPENAI_API_KEY"):
#     raise ValueError("OPENAI_API_KEY environment variable not set.")

# You might need to download the fastText language identification model
# FASTTEXT_MODEL_PATH = "lid.176.bin" # Or the path where you store it
# if not os.path.exists(FASTTEXT_MODEL_PATH):
#    print(f"FastText model not found at {FASTTEXT_MODEL_PATH}. Please download it.")
    # raise FileNotFoundError(f"FastText model not found at {FASTTEXT_MODEL_PATH}")
# fasttext_model = fasttext.load_model(FASTTEXT_MODEL_PATH)


def detect_language_fasttext(audio_path_or_text: str, model) -> str | None:
    """
    Detects language using fastText.
    This function expects text, so if an audio_path is given, it implies
    it should be transcribed first or this is a placeholder for a more complex
    scenario where text is extracted from audio by other means for fastText.
    For this implementation, we'll assume it's for text primarily.
    If using with audio, one would typically transcribe a small chunk first.
    """
    try:
        # For simplicity, this example won't directly process audio with fasttext
        # as fastText typically works on text. A real implementation might transcribe
        # a small portion or use a library that feeds audio features to a language ID model.
        # Here, we'll simulate it by requiring text or returning None for audio_path.
        if not isinstance(audio_path_or_text, str) or os.path.exists(audio_path_or_text):
             # This is a placeholder if we were to use fastText on a text snippet from audio
            print("Warning: detect_language_fasttext called with a path, needs text input or pre-transcription.")
            return None

        predictions = model.predict(audio_path_or_text.replace("\\n", " "), k=1) # Process first line or whole text
        lang_code = predictions[0][0].replace('__label__', '')
        confidence = predictions[1][0]
        # Set a confidence threshold, e.g., 0.5
        if confidence > 0.5:
            return lang_code
        return None
    except Exception as e:
        print(f"FastText language detection error: {e}")
        return None

def detect_language_langdetect(text: str) -> str | None:
    """Detects language using langdetect."""
    try:
        return detect(text)
    except lang_detect_exception.LangDetectException: # Handles cases like empty string or no features found
        return None
    except Exception as e:
        print(f"Langdetect error: {e}")
        return None


def transcribe_audio(audio_path: str, output_json_path: str, fasttext_model_path: str = "lid.176.bin"):
    """
    Transcribes an audio file using OpenAI Whisper, performs language detection,
    and saves the verbose JSON output.

    Args:
        audio_path: Path to the input audio file.
        output_json_path: Path to save the JSON transcription.
        fasttext_model_path: Path to the fastText language identification model.

    Returns:
        bool: True if transcription was successful, False otherwise.
    """
    if not os.path.exists(audio_path):
        print(f"Error: Audio file not found at {audio_path}")
        return False

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
        return False

    openai.api_key = os.getenv("OPENAI_API_KEY")

    # Language detection
    detected_lang = None

    # Attempt with fastText (requires a text snippet, Whisper will give us text later)
    # For now, we'll rely on Whisper's detection first, then try our detectors if needed.
    # If Whisper fails or language is ambiguous, one might transcribe a small chunk first
    # for language detection, but Whisper's own detection is usually quite good.

    try:
        with open(audio_path, "rb") as audio_file:
            # Use Whisper for transcription
            # If language is known, it can be passed as an argument: language="en"
            transcript = openai.Audio.transcribe(
                model="whisper-1", # Using "whisper-1" as it's the general API endpoint for the latest large model.
                                   # large-v3 is implicitly used by OpenAI if not specifying older versions.
                file=audio_file,
                response_format="verbose_json",
                # language=detected_lang # Optionally pass detected language
            )

        transcription_data = transcript # Already a dict from verbose_json

        # Whisper's response includes a 'language' field.
        whisper_lang = transcription_data.get("language")

        final_lang = whisper_lang # Prioritize Whisper's detection

        # If Whisper's language is unknown or needs confirmation, you could use fallback here.
        # For this example, we trust Whisper's detection if available.
        # If not, we could try our detectors on the transcribed text.
        if not final_lang or final_lang == "unknown": # 'unknown' is a placeholder, actual value might vary
            full_text_for_detection = transcription_data.get("text", "")
            if full_text_for_detection:
                # Try fastText on the transcribed text
                if os.path.exists(fasttext_model_path):
                    ft_model = fasttext.load_model(fasttext_model_path)
                    detected_lang_ft = detect_language_fasttext(full_text_for_detection, ft_model)
                    if detected_lang_ft:
                        final_lang = detected_lang_ft

                # Fallback to langdetect if fastText didn't yield a result
                if not final_lang or final_lang == "unknown":
                    detected_lang_ld = detect_language_langdetect(full_text_for_detection)
                    if detected_lang_ld:
                        final_lang = detected_lang_ld

            if not final_lang: # If still no language, default to "en" or handle as error
                print("Warning: Language could not be confidently determined. No language field will be set.")


        # Add the determined language to the top level of the JSON
        if final_lang and final_lang != "unknown":
            transcription_data["language"] = final_lang
        elif "language" in transcription_data and transcription_data["language"] == "unknown":
            # Remove unknown if we couldn't determine it better
            del transcription_data["language"]


        # Save the transcription
        output_dir = os.path.dirname(output_json_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(transcription_data, f, ensure_ascii=False, indent=4)

        print(f"Transcription saved to {output_json_path}")
        return True

    except openai.APIError as e:
        print(f"OpenAI API error: {e}")
    except openai.AuthenticationError as e:
        print(f"OpenAI Authentication Error: {e}. Check your API key.")
    except openai.RateLimitError as e:
        print(f"OpenAI Rate Limit Error: {e}.")
    except FileNotFoundError as e: # Specifically for fastText model
        print(f"Error: {e}. Ensure fastText model 'lid.176.bin' is available.")
    except Exception as e:
        print(f"An unexpected error occurred during transcription: {e}")

    return False

if __name__ == '__main__':
    # Example usage (requires a dummy audio file and API key)
    # Create a dummy audio file for testing if you don't have one
    # e.g., open("dummy_audio.mp3", "w").write("dummy content")
    # Set OPENAI_API_KEY in your environment

    # Before running, ensure you have:
    # 1. An OpenAI API Key set as an environment variable OPENAI_API_KEY
    # 2. The fastText model file 'lid.176.bin' in your working directory or specify path.
    #    Download from: https://fasttext.cc/docs/en/language-identification.html
    # 3. A sample audio file (e.g., audio.mp3)

    # Create dummy files and dirs for a simple test scenario
    if not os.path.exists("output"):
        os.makedirs("output")
    if not os.path.exists("dummy_audio.mp3"):
        with open("dummy_audio.mp3", "w") as f: # Not a real MP3, Whisper will fail
            f.write("This is not a real audio file.")

    # Check for fasttext model
    FASTTEXT_MODEL_PATH = "lid.176.bin"
    if not os.path.exists(FASTTEXT_MODEL_PATH):
        print(f"Warning: FastText model not found at {FASTTEXT_MODEL_PATH}. Language detection with fastText will be skipped.")
        print("Download it from https://fasttext.cc/docs/en/language-identification.html (lid.176.bin)")
        # For this example, we'll allow it to proceed without fasttext if model not present
        # by checking path existence in transcribe_audio

    # print("Attempting transcription (this will likely fail with dummy audio but tests structure):")
    # success = transcribe_audio("dummy_audio.mp3", "output/transcription.json", fasttext_model_path=FASTTEXT_MODEL_PATH)
    # print(f"Transcription attempt finished. Success: {success}")

    # To run a real test:
    # 1. Replace "dummy_audio.mp3" with a path to a real audio file.
    # 2. Ensure OPENAI_API_KEY is correctly set in your environment.
    # 3. Ensure lid.176.bin is present.
    # Example:
    # if os.getenv("OPENAI_API_KEY") and os.path.exists(FASTTEXT_MODEL_PATH) and os.path.exists("path_to_real_audio.mp3"):
    #    transcribe_audio("path_to_real_audio.mp3", "output/real_transcription.json", fasttext_model_path=FASTTEXT_MODEL_PATH)
    # else:
    #    print("Skipping real transcription test due to missing API key, fastText model, or audio file.")
    pass
