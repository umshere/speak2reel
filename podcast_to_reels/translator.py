import openai
import os
import json

# Ensure OPENAI_API_KEY is set, typically done globally at app start
# or checked before making calls.
# from dotenv import load_dotenv
# load_dotenv()
# if not os.getenv("OPENAI_API_KEY"):
#     raise ValueError("OPENAI_API_KEY environment variable not set.")

def translate_text(text_to_translate: str, target_language: str = "en", source_language: str = None) -> str | None:
    """
    Translates a given text to the target language using OpenAI's GPT-4o model.

    Args:
        text_to_translate: The text string to be translated.
        target_language: The language code for the target language (e.g., "en", "es", "fr").
                         Defaults to "en".
        source_language: Optional. The language code of the source text.
                         If provided, it's included in the prompt for better accuracy.

    Returns:
        The translated text as a string, or None if an error occurs.
    """
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
        return None

    openai.api_key = os.getenv("OPENAI_API_KEY")

    if not text_to_translate:
        return "" # Return empty string if input is empty

    # Construct the prompt
    if source_language:
        prompt = f"Translate the following {source_language} text to {target_language}:\n\n{text_to_translate}"
    else:
        prompt = f"Translate the following text to {target_language}:\n\n{text_to_translate}"

    try:
        client = openai.OpenAI() # Uses OPENAI_API_KEY from env by default
        response = client.chat.completions.create(
            model="gpt-4o", # Specify the GPT-4o model
            messages=[
                {"role": "system", "content": "You are a helpful translation assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3, # Lower temperature for more deterministic translation
            max_tokens=int(len(text_to_translate) * 2.5) # Estimate max tokens, adjust as needed
        )

        translated_text = response.choices[0].message.content.strip()
        return translated_text

    except openai.APIError as e:
        print(f"OpenAI API error: {e}")
    except openai.AuthenticationError as e:
        print(f"OpenAI Authentication Error: {e}. Check your API key.")
    except openai.RateLimitError as e:
        print(f"OpenAI Rate Limit Error: {e}.")
    except Exception as e:
        print(f"An unexpected error occurred during translation: {e}")

    return None

if __name__ == '__main__':
    # Example Usage (requires OPENAI_API_KEY to be set in the environment)
    # from dotenv import load_dotenv
    # load_dotenv() # Load .env file if you're using one

    if not os.getenv("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable to run this example.")
    else:
        print("OpenAI API Key found.")
        sample_text_es = "Hola, ¿cómo estás hoy? Espero que tengas un buen día."
        sample_text_fr = "Bonjour, comment ça va aujourd'hui? J'espère que vous passez une bonne journée."

        print(f"\nOriginal Spanish: {sample_text_es}")
        translated_to_en = translate_text(sample_text_es, target_language="en", source_language="es")
        if translated_to_en:
            print(f"Translated to English: {translated_to_en}")

        translated_to_fr = translate_text(sample_text_es, target_language="fr", source_language="es")
        if translated_to_fr:
            print(f"Translated to French: {translated_to_fr}")

        print(f"\nOriginal French: {sample_text_fr}")
        translated_fr_to_en = translate_text(sample_text_fr, target_language="en", source_language="fr")
        if translated_fr_to_en:
            print(f"Translated to English: {translated_fr_to_en}")

        # Example without source language (let GPT-4o detect)
        unknown_source_text = "Wie geht es Ihnen heute?" # German
        print(f"\nOriginal (unknown source): {unknown_source_text}")
        translated_unknown_to_en = translate_text(unknown_source_text, target_language="en")
        if translated_unknown_to_en:
            print(f"Translated to English (auto-detected source): {translated_unknown_to_en}")

        # Example of translating English to Spanish
        english_text = "Hello, how are you doing today? I hope you have a great day."
        print(f"\nOriginal English: {english_text}")
        translated_en_to_es = translate_text(english_text, target_language="es", source_language="en")
        if translated_en_to_es:
            print(f"Translated to Spanish: {translated_en_to_es}")

        # Test empty string
        print("\nTesting with empty string:")
        translated_empty = translate_text("", target_language="es")
        print(f"Translated empty string: '{translated_empty}' (should be empty)")
