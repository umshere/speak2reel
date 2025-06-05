from PIL import Image, ImageDraw

def create_image(filepath, size, color, text):
    img = Image.new('RGB', size, color=color)
    draw = ImageDraw.Draw(img)

    # Simple text in the middle
    try:
        # Basic font, might need to ensure a font file is available for more complex text
        # For simplicity, Pillow's default font will be used if available, or none if not.
        # Text rendering without a specific font file can be very basic.
        text_bbox = draw.textbbox((0,0), text) # Get bounding box
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        x = (size[0] - text_width) / 2
        y = (size[1] - text_height) / 2
        draw.text((x, y), text, fill=(0,0,0)) # Black text
    except Exception as e:
        print(f"Could not draw text due to: {e}. Image will be blank color.")

    img.save(filepath)
    print(f"Saved image: {filepath}")

if __name__ == "__main__":
    output_dir = "output/images"
    if not Image: # Should not happen if Pillow installed
        print("Pillow (PIL) is not available. Cannot create images.")
        exit(1)

    # Create 1080x1920 images
    create_image(f"{output_dir}/sample_scene_0.png", (1080, 1920), 'lightblue', "Scene 0")
    create_image(f"{output_dir}/sample_scene_1.png", (1080, 1920), 'lightgreen', "Scene 1")
    create_image(f"{output_dir}/sample_scene_2.png", (1080, 1920), 'lightcoral', "Scene 2")

    # Create a smaller, different aspect ratio image for variety
    create_image(f"{output_dir}/sample_scene_3_small.png", (600, 400), 'lightgoldenrodyellow', "Scene 3 Small")

    print("Sample images created.")
