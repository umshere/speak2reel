# Podcast to Reels Pipeline

This project provides an automated pipeline to convert segments from podcasts or YouTube videos into engaging short video reels, suitable for social media platforms. It leverages AI for audio transcription, language translation (optional), image prompt generation, and image creation, then composes these elements into a final video with subtitles.

## Features

*   **Automated Audio Extraction**: Downloads audio from YouTube URLs.
*   **AI-Powered Transcription**: Utilizes OpenAI Whisper for accurate audio transcription.
*   **Multilingual Support**:
    *   Detects audio language using Whisper, with fallbacks to FastText and Langdetect.
    *   Optionally translates non-English transcripts to English for image prompt generation and subtitles.
*   **AI Scene & Image Prompt Generation**: Splits transcripts into logical scenes and uses OpenAI GPT-4o-mini to generate vivid image prompts for each scene.
*   **AI Image Generation**: Creates images for scenes using Stability AI SD3.
*   **Automated Video Composition**: Combines audio, generated images, and subtitles into a vertical video reel (MP4 format).
*   **Subtitle Generation**:
    *   Supports subtitles in the original language, translated English, or both.
    *   Generates SRT subtitle files as artifacts.
*   **Customizable**: Output duration, subtitle preferences, and output directories can be configured via command-line arguments.

## Architecture

The pipeline consists of several modules that process data sequentially:

```mermaid
graph TD
    A[Input: YouTube URL] --> B(Module 1: Downloader);
    B -- Audio Path & Max Duration --> C{{downloaded_audio.mp3}};
    C --> D(Module 2a: Transcriber);
    D -- Audio Path, FastText Model Path --> E{{original_transcript.json (Segments, Timestamps, Language)}};
    E --> F{Need Translation for Subtitles/Prompts?};
    F -- Yes, Non-English & 'en'/'both' subs --> G(Module 2b: Translator);
    G -- Segments to Translate, Target Lang 'en' --> H{{english_translation.json}};
    F -- No --> I(Module 3: Scene Splitter & Prompt Builder);
    E --> I; % Original transcript for scene text
    I -- Transcript Data --> J{{Scene Data (Text Chunks, Timings, English Image Prompts)}};
    J --> K(Module 4: Image Generator);
    K -- English Image Prompts, Output Dir, Scene Index --> L{{Generated Images (scene_X.png)}};
    C --> M(Module 5: Video Composer);
    L --> M;
    J --> M; % Scene timings and text for reference
    E --> M; % For 'orig' subtitles
    H ==> M; % For 'en' subtitles (double arrow for optional flow)
    M -- Audio, Images, Scene Data, Subtitle Config --> N{{final_reel.mp4}};
    M -- Transcript Data (orig/en) --> O{{reel_lang.srt}};
```

## Setup Instructions

### Prerequisites

*   **Python**: Version 3.11 or higher.
*   **Poetry**: For dependency management. ([Installation Guide](https://python-poetry.org/docs/#installation))
*   **FFmpeg**: Required by MoviePy for video processing. ([Installation Guide](https://ffmpeg.org/download.html)) Ensure it's installed and accessible in your system's PATH.

### Installation Steps

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/podcast-to-reels.git # Replace with actual repo URL
    cd podcast-to-reels
    ```

2.  **Install dependencies using Poetry**:
    ```bash
    poetry install --with dev # Installs main and development dependencies
    ```

3.  **Environment Variables**:
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and fill in your API keys:
        *   `OPENAI_API_KEY`: Your OpenAI API key (for Whisper, GPT).
        *   `STABILITY_API_KEY`: Your Stability AI API key (for image generation).
    *   **FastText Model (Optional but Recommended for non-English audio)**:
        *   The pipeline uses FastText for language detection fallback. The default expected model file is `lid.176.bin`.
        *   Download the model from the [FastText website (language identification section)](https://fasttext.cc/docs/en/language-identification.html). Look for the "Binary model" link for `lid.176.bin`.
        *   Place the downloaded `lid.176.bin` in the project's root directory (or any other location).
        *   If you place it elsewhere, set the `FASTTEXT_MODEL_PATH` in your `.env` file or use the `--fasttext_model_path` command-line argument when running the pipeline.
        Example `.env` entry:
        ```
        FASTTEXT_MODEL_PATH="path/to/your/lid.176.bin"
        ```

## Usage

The main pipeline is executed via the `scripts/run_pipeline.py` script.

**Basic Run (Defaults: 60s duration, no subtitles, output to `./output/`):**
```bash
poetry run python scripts/run_pipeline.py --url <YOUTUBE_URL>
```
Replace `<YOUTUBE_URL>` with the actual URL of the YouTube video.

**With Specific Duration and "Both" Subtitles:**
This will create a 30-second reel with both original language and English subtitles (if the original language is not English).
```bash
poetry run python scripts/run_pipeline.py --url <YOUTUBE_URL> --duration 30 --subtitles both
```

**Specifying Output Directory:**
```bash
poetry run python scripts/run_pipeline.py --url <YOUTUBE_URL> --output_dir my_reels
```

**Full list of options:**
Use `poetry run python scripts/run_pipeline.py --help` to see all available command-line arguments.

## Output Artifacts

The pipeline generates several artifacts, typically found in the `output/` directory (or your specified `--output_dir`):

*   **`downloaded_audio.mp3`**: The audio file downloaded and trimmed from the YouTube URL.
*   **`transcripts/`**:
    *   `original_transcript.json`: The full transcription output from Whisper in the detected original language (verbose JSON format).
    *   `english_translation.json` (optional): If translation was performed, this contains the English version of the transcript.
    *   `scenes_with_prompts.json`: Data about each scene, including its text, timing, and the AI-generated image prompt.
    *   `reel_orig.srt` / `reel_en.srt` (optional): Subtitle files in SRT format.
*   **`images/`**: Contains the AI-generated images for each scene (e.g., `scene_0.png`, `scene_1.png`, ...).
*   **`final_reel.mp4`**: The composed video reel with images, audio, and burned-in subtitles (if requested).

Sample output files are available in the `output/` directory of this repository for reference.

## Multilingual Considerations

*   **Language Detection**: The system first relies on Whisper's language detection. If needed, `transcribe_audio` can use FastText and Langdetect as fallbacks to determine the language of the audio.
*   **Transcription**: Whisper can transcribe audio in various languages.
*   **Translation**: If the detected language is not English and English subtitles or prompts are desired (for image generation, which works best with English prompts), the `Translator` module (using GPT-4o) will translate the transcript segments.
*   **Subtitles**: The `--subtitles` option controls subtitle generation:
    *   `none`: No subtitles.
    *   `orig`: Subtitles in the original language of the podcast.
    *   `en`: Subtitles translated into English.
    *   `both`: Both original language and English subtitles displayed (original typically above English).

## Cost Estimation (Brief)

Running this pipeline involves costs from third-party APIs:

*   **OpenAI API**:
    *   Whisper for transcription (priced per minute of audio).
    *   GPT-4o or similar for translation and image prompt generation (priced per token).
*   **Stability AI API**:
    *   SD3 or similar for image generation (priced per image).

**Rough Estimate**: For a 60-second reel involving transcription, translation of ~500 words, generation of ~5 image prompts, and 5 images, the cost might be in the range of **US$0.10 - US$0.30**. This is highly dependent on the exact length of text processed by GPT models and the number of images generated. The project aims to stay below US$0.30 per demo reel as per the initial brief. Always check the latest pricing for OpenAI and Stability AI.

## Troubleshooting/FAQ

*   **"FFmpeg not found" error during video composition**:
    *   Ensure FFmpeg is correctly installed on your system and that its executable is in your system's PATH. Refer to the [FFmpeg download page](https://ffmpeg.org/download.html).
*   **"FastText model `lid.176.bin` not found"**:
    *   Download the `lid.176.bin` model from the [FastText website (language identification section)](https://fasttext.cc/docs/en/language-identification.html).
    *   Place it in the location specified by `FASTTEXT_MODEL_PATH` in your `.env` file, or provide the correct path via the `--fasttext_model_path` argument when running the script. If no path is set, the script might look in the root directory by default.
*   **API Errors (401 Unauthorized, 429 Rate Limit, etc.)**:
    *   Double-check your API keys in the `.env` file.
    *   Ensure your API accounts have sufficient credits or are not exceeding rate limits.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
```
