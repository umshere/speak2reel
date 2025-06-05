from celery import shared_task
from webapp.jobs.models import VideoProject
import os
import subprocess
import json

def get_style_prefix(style_key):
    style_map = {
        'photorealistic': 'A photorealistic, high-detail image of: ',
        'cartoon': 'A cartoon style illustration of: ',
        'abstract': 'An abstract artistic interpretation of: ',
        'pixel_art': 'Pixel art of: ',
        'line_art': 'A black and white line art drawing of: ',
        'fantasy': 'A fantasy art painting of: ',
        'anime': 'An anime style drawing of: ',
        'default': ''
    }
    return style_map.get(style_key, '')

@shared_task(bind=True)
def process_video_pipeline_task(self, video_project_id, youtube_url, duration, subtitles, video_format, output_dir_base, initial_run=True):
    task_id = self.request.id
    video_project = None
    try:
        video_project = VideoProject.objects.get(pk=video_project_id)
        if initial_run and (video_project.status == 'PENDING' or not video_project.status):
            video_project.status = 'PROCESSING'
        video_project.celery_task_id = task_id
        video_project.save()
    except VideoProject.DoesNotExist:
        print(f'CRITICAL ERROR: VideoProject with ID {video_project_id} not found.')
        raise Exception(f'VideoProject ID {video_project_id} not found.')
    except Exception as e:
        print(f'CRITICAL DB ERROR: Could not update VideoProject {video_project_id}: {e}')
        raise Exception(f'DB error for VideoProject {video_project_id}: {e}')

    job_specific_output_dir = os.path.join(output_dir_base, str(video_project.id))
    os.makedirs(job_specific_output_dir, exist_ok=True)
    if not video_project.job_output_path_segment:
        video_project.job_output_path_segment = str(video_project.id) # Store just the ID part
        video_project.save()

    scenes_json_path_in_pipeline_output = os.path.join(job_specific_output_dir, 'transcripts', 'scenes_with_prompts.json')

    if initial_run and not video_project.scenes_data:
        video_project.status = 'SPLITTING_SCENES'
        video_project.save()

        # Call pipeline to generate scenes.json
        pipeline_script_path = '../scripts/run_pipeline.py'
        command_scene_gen = [
            'python', pipeline_script_path, '--url', youtube_url, '--duration', str(duration),
            '--subtitles', subtitles, '--video_format', video_format,
            '--output_dir', job_specific_output_dir,
            # Add hypothetical flag to tell script to stop after scene generation
            # '--target_stage', 'scene_splitting_and_prompts'
        ]
        print(f'Executing scene generation command: {" ".join(command_scene_gen)}')
        try:
            # In a real app, this subprocess call might need to pass environment variables (API keys).
            process_scene_gen = subprocess.Popen(command_scene_gen, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            sc_stdout, sc_stderr = process_scene_gen.communicate(timeout=1800)

            if process_scene_gen.returncode == 0 and os.path.exists(scenes_json_path_in_pipeline_output):
                with open(scenes_json_path_in_pipeline_output, 'r') as f:
                    video_project.scenes_data = json.load(f)
                video_project.status = 'AWAITING_USER_INPUT'
                video_project.save()
                return {'status': 'AWAITING_USER_INPUT', 'message': 'Scenes generated. Review prompts and style.'}
            else:
                err_msg = f'Scene generation failed. Code: {process_scene_gen.returncode}. Stderr: {sc_stderr.decode("utf-8", "ignore")}'
                video_project.status = 'FAILED'; video_project.error_message = err_msg; video_project.save()
                raise Exception(err_msg)
        except Exception as e:
            video_project.status = 'FAILED'; video_project.error_message = f'Error in scene generation stage: {str(e)}'; video_project.save()
            raise

    if not video_project.scenes_data:
        video_project.status = 'FAILED'; video_project.error_message = 'Scenes data missing for image/video processing.'; video_project.save()
        raise Exception('Scenes data missing for image/video processing.')

    video_project.status = 'GENERATING_IMAGES'
    video_project.save()

    style_prefix = get_style_prefix(video_project.image_style_preference)
    final_scenes_for_pipeline = []
    for scene in video_project.scenes_data:
        current_prompt = scene['image_prompt']
        full_prompt = style_prefix + current_prompt
        if video_project.positive_style_keywords:
            full_prompt += ', ' + video_project.positive_style_keywords
        if video_project.artist_influences:
            full_prompt += ', art by ' + video_project.artist_influences

        # Negative keywords need to be handled by the image generation script itself.
        # We are not adding them to the positive prompt.
        final_scenes_for_pipeline.append({**scene, 'image_prompt': full_prompt.strip()})

    # Save the fully styled prompts for the pipeline script to use
    final_prompts_input_file = os.path.join(job_specific_output_dir, 'transcripts', 'final_prompts_for_image_gen.json')
    with open(final_prompts_input_file, 'w') as f:
        json.dump(final_scenes_for_pipeline, f)

    pipeline_script_path = '../scripts/run_pipeline.py'
    command_video_gen = [
        'python', pipeline_script_path, '--url', youtube_url, '--duration', str(duration),
        '--subtitles', subtitles, '--video_format', video_project.video_format_preference,
        '--output_dir', job_specific_output_dir,
        # The pipeline script needs to be adapted to:
        # 1. Read prompts from 'final_prompts_for_image_gen.json' if it exists.
        # 2. Accept 'negative_style_keywords' and pass them to the image generator.
        # '--prompt_file', final_prompts_input_file, # Hypothetical
        # '--negative_keywords', video_project.negative_style_keywords, # Hypothetical
        # '--skip_scene_splitting' # Hypothetical
    ]
    print(f'Executing image/video generation with styled prompts: {" ".join(command_video_gen)}')

    try:
        process_video_gen = subprocess.Popen(command_video_gen, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        vg_stdout, vg_stderr = process_video_gen.communicate(timeout=3600)
        if process_video_gen.returncode == 0:
            video_project.status = 'COMPLETED'
            video_project.final_video_path = os.path.join(str(video_project.id), 'final_reel.mp4') # Relative to JOBS_BASE_OUTPUT_DIR
            video_project.error_message = None
        else:
            video_project.status = 'FAILED'
            video_project.error_message = f'Image/Video generation failed. Code: {process_video_gen.returncode}. Stderr: {vg_stderr.decode("utf-8", "ignore")}'
        video_project.save()
        return {'status': video_project.status, 'output_dir_segment': str(video_project.id), 'final_video_path': video_project.final_video_path}
    except Exception as e:
        video_project.status = 'FAILED'; video_project.error_message = f'Error in image/video generation stage: {str(e)}'; video_project.save()
        raise
