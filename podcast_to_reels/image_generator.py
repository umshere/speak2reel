import requests
import os
import time
import base64

# Ensure STABILITY_API_KEY is set
# from dotenv import load_dotenv
# load_dotenv()
# if not os.getenv("STABILITY_API_KEY"):
#     raise ValueError("STABILITY_API_KEY environment variable not set.")

STABILITY_API_HOST = "https://api.stability.ai"
# Using sd3-medium as sd3.5-medium is not a valid model name as per Stability AI documentation (as of June 2024)
# Refer to: https://platform.stability.ai/docs/api-reference#tag/Generate/paths/~1v2beta~1stable-image~1generate~1sd3/post
# If sd3.5-medium becomes available, this can be updated.
STABILITY_ENGINE_ID = "sd3-medium"


def generate_image_from_prompt(prompt: str, output_image_dir: str, scene_index: int) -> bool:
    """
    Generates an image using Stability AI SD3 API based on a prompt and saves it.

    Args:
        prompt: The English prompt for image generation.
        output_image_dir: The directory where the image will be saved.
        scene_index: An index for naming the output file (e.g., scene_{scene_index}.png).

    Returns:
        True if image generation and saving were successful, False otherwise.
    """
    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        print("Error: STABILITY_API_KEY environment variable not set.")
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

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "image/png", # Request PNG directly
    }

    # For SD3, the endpoint is /v2beta/stable-image/generate/sd3
    # Payload for SD3 (differs from older models)
    data = {
        "prompt": prompt,
        "aspect_ratio": "9:16", # For vertical reels
        "output_format": "png", # Explicitly request png
        "model": STABILITY_ENGINE_ID, # Specify the model
        # "mode": "text-to-image", # Default mode for SD3
        # "strength": 0.8, # Optional: for image-to-image, not used here
    }

    # The SD3 API uses multipart/form-data, not application/json
    files = {key: (None, str(value)) for key, value in data.items()}


    max_retries = 2
    retry_delay = 2  # seconds

    for attempt in range(max_retries + 1):
        try:
            # Note: Stability AI API documentation for SD3 suggests using 'files' for multipart/form-data
            # Ref: https://platform.stability.ai/docs/api-reference#tag/Generate/paths/~1v2beta~1stable-image~1generate~1sd3/post
            response = requests.post(
                f"{STABILITY_API_HOST}/v2beta/stable-image/generate/sd3",
                headers=headers,
                files=files # Send as multipart/form-data
            )
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)

            # If successful, the response content is the image bytes
            with open(output_image_path, "wb") as f:
                f.write(response.content)
            print(f"Image saved successfully to {output_image_path}")
            return True

        except requests.exceptions.HTTPError as e:
            print(f"HTTP error occurred: {e} - Status Code: {e.response.status_code}")
            if e.response.status_code == 401:
                print("Authentication error. Check your STABILITY_API_KEY.")
                return False # No retry on auth error
            if e.response.status_code == 403: # Forbidden, possibly billing
                print("Forbidden error. This might be due to billing issues or insufficient credits.")
                try:
                    print(f"Error details from API: {e.response.json()}")
                except ValueError:
                    print(f"Raw error response: {e.response.text}")
                return False # No retry
            if e.response.status_code == 400: # Bad request, e.g. invalid prompt
                 print(f"Bad request (400). Invalid prompt or parameters? API response: {e.response.text}")
                 return False # No retry

            if 500 <= e.response.status_code < 600: # Server-side error
                if attempt < max_retries:
                    print(f"Server error ({e.response.status_code}). Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(retry_delay)
                else:
                    print(f"Server error ({e.response.status_code}) after {max_retries +1} attempts. Giving up.")
                    return False
            else: # Other client-side errors
                return False # Do not retry for other client errors
        except requests.exceptions.RequestException as e: # Catch other request exceptions (network, timeout)
            print(f"A request exception occurred: {e}")
            if attempt < max_retries:
                print(f"Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(retry_delay)
            else:
                print(f"Request exception after {max_retries + 1} attempts. Giving up.")
                return False
        except IOError as e:
            print(f"File saving error: {e}")
            return False # Error during file operation
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return False # Catch any other unexpected errors

    return False # Should be unreachable if logic is correct, but as a fallback.


if __name__ == '__main__':
    # Example Usage (requires STABILITY_API_KEY to be set)
    # from dotenv import load_dotenv
    # load_dotenv()

    if not os.getenv("STABILITY_API_KEY"):
        print("Please set the STABILITY_API_KEY environment variable to run this example.")
    else:
        print("Stability API Key found.")
        sample_prompt = "A futuristic cityscape with flying cars, modern flat-style illustration, vibrant colors."
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

        # Example of a potentially problematic prompt (e.g., if it violates safety guidelines)
        # Note: Stability API has its own safety filters.
        # problematic_prompt = "a controversial political cartoon"
        # print(f"\nGenerating image for a potentially problematic prompt: '{problematic_prompt}'")
        # success_problematic = generate_image_from_prompt(problematic_prompt, output_directory, scene_index=1)
        # if success_problematic:
        #     print(f"Image generation successful (problematic). Check '{output_directory}/scene_1.png'")
        # else:
        #     print("Image generation failed (problematic), as expected or due to an error.")

        # Test empty prompt
        print("\nTesting with empty prompt:")
        success_empty = generate_image_from_prompt("", output_directory, scene_index=2)
        if not success_empty:
            print("Image generation failed for empty prompt, as expected.")
        else:
            print("Image generation succeeded for empty prompt (unexpected).")

```
