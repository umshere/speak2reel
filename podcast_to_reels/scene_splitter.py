import openai
import os
import json # For potential debugging or data handling, not strictly required by current plan

# Ensure OPENAI_API_KEY is set
# from dotenv import load_dotenv
# load_dotenv()
# if not os.getenv("OPENAI_API_KEY"):
#     raise ValueError("OPENAI_API_KEY environment variable not set.")

def generate_image_prompt_with_openai(text_chunk: str, language: str = "en") -> str | None:
    """
    Generates a vivid, concise English image prompt using OpenAI GPT-4o-mini.
    If the input text is not English, its meaning is translated to English first.

    Args:
        text_chunk: The text to base the prompt on.
        language: The language of the text_chunk.

    Returns:
        The generated English image prompt, or None if an error occurs.
    """
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set for image prompt generation.")
        return None

    openai.api_key = os.getenv("OPENAI_API_KEY")

    client = openai.OpenAI()

    prompt_instruction = (
        f"Based on the following text (which is in {language}), generate a concise and visually descriptive English prompt for an AI image generator. "
        "The prompt should be suitable for creating a modern flat-style illustration. "
        "If the text is not in English, understand its meaning and generate an English prompt that captures the essence for the illustration. "
        f"Text: '{text_chunk}'"
    )
    if language.lower() == "en":
        prompt_instruction = (
            "Based on the following English text, generate a concise and visually descriptive English prompt for an AI image generator. "
            "The prompt should be suitable for creating a modern flat-style illustration. "
            f"Text: '{text_chunk}'"
    )


    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert prompt generator for AI image creation, specializing in modern flat-style illustrations. Ensure all output prompts are in English."},
                {"role": "user", "content": prompt_instruction}
            ],
            temperature=0.5, # Slightly creative but still grounded
            max_tokens=100 # Image prompts are usually short
        )
        image_prompt = response.choices[0].message.content.strip()
        # Clean up common "Prompt:" prefix if the model adds it.
        if image_prompt.lower().startswith("prompt:"):
            image_prompt = image_prompt[len("prompt:"):].strip()
        return image_prompt
    except openai.APIError as e:
        print(f"OpenAI API error during image prompt generation: {e}")
    except openai.AuthenticationError as e:
        print(f"OpenAI Authentication Error: {e}. Check your API key.")
    except openai.RateLimitError as e:
        print(f"OpenAI Rate Limit Error: {e}.")
    except Exception as e:
        print(f"An unexpected error occurred during image prompt generation: {e}")
    return None


def split_transcript_into_scenes(transcript_data: dict, words_per_chunk: int = 20) -> list[dict]:
    """
    Splits a transcript into scenes (chunks) of around `words_per_chunk` words,
    respecting segment boundaries, and generates an English image prompt for each scene.

    Args:
        transcript_data: A dictionary from the Transcriber module, containing:
                         - 'language' (str): The language of the transcript.
                         - 'segments' (list): A list of dicts, each with 'text', 'start', and 'end'.
        words_per_chunk: The target number of words for each scene/chunk.

    Returns:
        A list of dictionaries, where each dictionary represents a scene and contains:
        - 'chunk_text' (str): The original text of the chunk.
        - 'start_time' (float): Start time of the chunk.
        - 'end_time' (float): End time of the chunk.
        - 'image_prompt' (str): The generated English image prompt.
                                Returns None for image_prompt if generation fails.
    """
    if not transcript_data or "segments" not in transcript_data or not transcript_data["segments"]:
        print("Warning: Transcript data is empty or malformed.")
        return []

    segments = transcript_data["segments"]
    source_language = transcript_data.get("language", "en") # Default to English if not specified

    scenes = []
    current_chunk_text = []
    current_chunk_word_count = 0
    chunk_start_time = -1.0
    chunk_end_time = -1.0

    for segment in segments:
        segment_text = segment.get("text", "").strip()
        segment_start = segment.get("start", 0.0)
        segment_end = segment.get("end", 0.0)

        if not segment_text:
            continue

        segment_words = segment_text.split()
        segment_word_count = len(segment_words)

        # If this segment alone is much larger than words_per_chunk,
        # process it as its own scene(s) or split it further (future enhancement).
        # For now, if a single segment is large, it becomes its own scene.
        if current_chunk_word_count == 0 and segment_word_count >= words_per_chunk * 1.5 :
            image_prompt = generate_image_prompt_with_openai(segment_text, source_language)
            scenes.append({
                "chunk_text": segment_text,
                "start_time": segment_start,
                "end_time": segment_end,
                "image_prompt": image_prompt
            })
            continue # Move to the next segment

        # If adding this segment exceeds the target word count (and we have some words already)
        # or if it's the last segment, finalize the current chunk.
        if current_chunk_word_count > 0 and (current_chunk_word_count + segment_word_count > words_per_chunk + 5) :
            full_chunk_text = " ".join(current_chunk_text)
            image_prompt = generate_image_prompt_with_openai(full_chunk_text, source_language)
            scenes.append({
                "chunk_text": full_chunk_text,
                "start_time": chunk_start_time,
                "end_time": chunk_end_time, # end time of the last segment added to this chunk
                "image_prompt": image_prompt
            })
            # Reset for the new chunk starting with the current segment
            current_chunk_text = [segment_text]
            current_chunk_word_count = segment_word_count
            chunk_start_time = segment_start
            chunk_end_time = segment_end
        else:
            # Add segment to current chunk
            if chunk_start_time < 0: # First segment of a new chunk
                chunk_start_time = segment_start

            current_chunk_text.append(segment_text)
            current_chunk_word_count += segment_word_count
            chunk_end_time = segment_end # Update end time to this segment's end

    # Add the last remaining chunk, if any
    if current_chunk_text:
        full_chunk_text = " ".join(current_chunk_text)
        image_prompt = generate_image_prompt_with_openai(full_chunk_text, source_language)
        scenes.append({
            "chunk_text": full_chunk_text,
            "start_time": chunk_start_time,
            "end_time": chunk_end_time,
            "image_prompt": image_prompt
        })

    return scenes

if __name__ == '__main__':
    # Example Usage (requires OPENAI_API_KEY to be set)
    # from dotenv import load_dotenv
    # load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable to run this example.")
    else:
        print("OpenAI API Key found.")
        sample_transcript_data_en = {
            "language": "en",
            "segments": [
                {"text": "Hello everyone and welcome back to the podcast.", "start": 0.5, "end": 3.5},
                {"text": "Today we're talking about the future of AI.", "start": 3.8, "end": 6.9},
                {"text": "It's a rapidly evolving field with many exciting developments.", "start": 7.2, "end": 11.5},
                {"text": "Let's dive into some of the latest trends.", "start": 12.0, "end": 14.5},
                {"text": "One major area is generative models, which can create text, images, and even music.", "start": 15.0, "end": 22.0},
                {"text": "Think about tools like DALL-E or GPT-4.", "start": 22.5, "end": 25.8},
                {"text": "They are becoming incredibly powerful.", "start": 26.0, "end": 28.5}
            ]
        }

        sample_transcript_data_es = {
            "language": "es",
            "segments": [
                {"text": "Hola a todos y bienvenidos de nuevo al podcast.", "start": 0.5, "end": 3.5},
                {"text": "Hoy hablaremos sobre el futuro de la inteligencia artificial.", "start": 3.8, "end": 7.9},
                {"text": "Es un campo que evoluciona rápidamente con muchos desarrollos emocionantes.", "start": 8.2, "end": 13.5},
                {"text": "Vamos a sumergirnos en algunas de las últimas tendencias.", "start": 14.0, "end": 17.0}
            ]
        }

        print("\n--- English Transcript Processing ---")
        scenes_en = split_transcript_into_scenes(sample_transcript_data_en, words_per_chunk=15)
        for i, scene in enumerate(scenes_en):
            print(f"\nScene {i+1}:")
            print(f"  Text: {scene['chunk_text']}")
            print(f"  Time: {scene['start_time']:.2f}s - {scene['end_time']:.2f}s")
            print(f"  Prompt: {scene['image_prompt']}")

        print("\n--- Spanish Transcript Processing (Prompts should be English) ---")
        scenes_es = split_transcript_into_scenes(sample_transcript_data_es, words_per_chunk=15)
        for i, scene in enumerate(scenes_es):
            print(f"\nScene {i+1}:")
            print(f"  Text: {scene['chunk_text']}")
            print(f"  Time: {scene['start_time']:.2f}s - {scene['end_time']:.2f}s")
            print(f"  Prompt: {scene['image_prompt']}")

        # Example with a very long single segment
        sample_transcript_long_segment = {
            "language": "en",
            "segments": [
                {"text": "This is a single very long segment designed to test the handling of segments that by themselves exceed the typical words_per_chunk limit, it just keeps going on and on to ensure that it forms its own scene rather than being merged unnecessarily or causing issues with the splitting logic which might expect multiple smaller segments.", "start": 0.0, "end": 15.0}
            ]
        }
        print("\n--- Long Single Segment Transcript Processing ---")
        scenes_long = split_transcript_into_scenes(sample_transcript_long_segment, words_per_chunk=10)
        for i, scene in enumerate(scenes_long):
            print(f"\nScene {i+1}:")
            print(f"  Text: {scene['chunk_text']}")
            print(f"  Time: {scene['start_time']:.2f}s - {scene['end_time']:.2f}s")
            print(f"  Prompt: {scene['image_prompt']}")

        # Example with empty segments
        sample_transcript_empty = {
            "language": "en",
            "segments": []
        }
        print("\n--- Empty Transcript Processing ---")
        scenes_empty = split_transcript_into_scenes(sample_transcript_empty, words_per_chunk=15)
        print(f"Scenes from empty transcript: {scenes_empty} (should be empty list)")
```
