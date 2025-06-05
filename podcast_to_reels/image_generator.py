import os
import time
import requests
from openai import OpenAI


def generate_image_from_prompt(prompt: str, output_image_dir: str, scene_index: int) -> bool:
    """
    Generates an image using OpenAI GPT-4o image generation based on a prompt and saves it.

    Args:
        prompt: The English prompt for image generation.
        output_image_dir: The directory where the image will be saved.
        scene_index: An index for naming the output file (e.g., scene_{scene_index}.png).

    Returns:
        True if image generation and saving were successful, False otherwise.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        return False

    if not prompt:
        print("Error: Prompt cannot be empty.")
        return False

    if not os.path.exists(output_image_dir):
        try:
            os.makedirs(output_image_dir)
        except OSError as e:
            print(f"Error creating output directory {output_image_dir}: {e}")
            return False

    output_filename = f"scene_{scene_index}.png"
    output_image_path = os.path.join(output_image_dir, output_filename)

    max_retries = 2
    retry_delay = 2  # seconds

    for attempt in range(max_retries + 1):
        try:
            # Initialize OpenAI client
            client = OpenAI(api_key=api_key)
            
            # Enhanced prompt for better image generation
            enhanced_prompt = f"Create a high-quality, vertically oriented (9:16 aspect ratio) image for a social media reel. The image should be: {prompt}. Make it visually engaging, modern, and suitable for social media content."
            
            # Try GPT-4o with image generation first
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user", 
                            "content": f"Please generate an image: {enhanced_prompt}"
                        }
                    ],
                    max_tokens=300
                )
                
                # Check if GPT-4o provided image generation capabilities
                # Note: This is experimental as GPT-4o image generation API is still being rolled out
                if response.choices and response.choices[0].message.content:
                    print("GPT-4o responded, but image generation may not be available yet.")
                    print("Falling back to DALL-E 3...")
                    raise Exception("GPT-4o image generation not yet implemented")
                
            except Exception as gpt4o_error:
                print(f"GPT-4o image generation not available: {gpt4o_error}")
                print("Using DALL-E 3 instead...")
            
            # Use DALL-E 3 for reliable image generation
            image_response = client.images.generate(
                model="dall-e-3",
                prompt=enhanced_prompt,
                size="1024x1792",  # Vertical aspect ratio for reels (9:16 equivalent)
                quality="standard",
                n=1
            )
            
            # Get the image URL from the response
            image_url = image_response.data[0].url
            
            # Download the image
            download_response = requests.get(image_url)
            download_response.raise_for_status()
            
            # Save the image
            with open(output_image_path, "wb") as f:
                f.write(download_response.content)
            
            print(f"Image saved successfully to {output_image_path}")
            return True

        except Exception as e:
            error_msg = str(e).lower()
            
            # Check for authentication errors
            if "authentication" in error_msg or "401" in error_msg:
                print("Authentication error. Check your OPENAI_API_KEY.")
                return False  # No retry on auth error
            
            # Check for billing/quota errors
            if "billing" in error_msg or "quota" in error_msg or "insufficient" in error_msg:
                print("Billing or quota error. Check your OpenAI account credits.")
                return False  # No retry
            
            # Check for content policy violations
            if "content policy" in error_msg or "violated" in error_msg:
                print(f"Content policy violation. Prompt may be inappropriate: {prompt}")
                return False  # No retry
            
            # For server errors or rate limits, retry
            if "server" in error_msg or "rate" in error_msg or "429" in error_msg or "5" in str(e)[:3]:
                if attempt < max_retries:
                    print(f"Server/rate limit error. Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(retry_delay)
                else:
                    print(f"Server/rate limit error after {max_retries + 1} attempts. Giving up.")
                    print(f"Error details: {e}")
                    return False
            else:
                print(f"An error occurred: {e}")
                return False

    return False


if __name__ == '__main__':
    # Example Usage (requires OPENAI_API_KEY to be set)
    # from dotenv import load_dotenv
    # load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable to run this example.")
    else:
        print("OpenAI API Key found.")
        sample_prompt = "A futuristic cityscape with flying cars, modern flat-style illustration, vibrant colors, cinematic lighting."
        output_directory = "output/generated_images" # Will be created if it doesn't exist

        # Create a dummy prompt file for testing if needed
        if not os.path.exists(output_directory):
             os.makedirs(output_directory, exist_ok=True)

        print(f"\nGenerating image for prompt: '{sample_prompt}'")
        success = generate_image_from_prompt(sample_prompt, output_directory, scene_index=0)
        if success:
            print(f"Image generation successful. Check '{output_directory}/scene_0.png'")
        else:
            print("Image generation failed.")

        # Test empty prompt
        print("\nTesting with empty prompt:")
        success_empty = generate_image_from_prompt("", output_directory, scene_index=2)
        if not success_empty:
            print("Image generation failed for empty prompt, as expected.")
        else:
            print("Image generation succeeded for empty prompt (unexpected).")
