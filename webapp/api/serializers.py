from rest_framework import serializers
from webapp.jobs.models import VideoProject

class VideoJobSubmitSerializer(serializers.Serializer):
    youtube_url = serializers.URLField()
    duration = serializers.IntegerField(default=60, min_value=5, max_value=600)
    subtitles = serializers.ChoiceField(choices=['none', 'orig', 'en', 'both'], default='none')
    video_format = serializers.ChoiceField(choices=VideoProject.VIDEO_FORMAT_CHOICES, default='9:16')

class VideoJobResponseSerializer(serializers.Serializer):
    job_id = serializers.CharField(read_only=True)
    video_project_id = serializers.IntegerField(read_only=True)
    status_url = serializers.URLField(read_only=True)
    message = serializers.CharField(read_only=True)

class VideoProjectListSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    class Meta:
        model = VideoProject
        fields = [
            'id', 'user', 'youtube_url', 'status',
            'image_style_preference', 'video_format_preference',
            'positive_style_keywords', 'negative_style_keywords', 'artist_influences', # Added
            'created_at', 'celery_task_id', 'final_video_path', 'is_public_in_gallery',
            'duration_seconds', 'subtitle_preference' # From dashboard step
        ]

class PublicVideoProjectSerializer(serializers.ModelSerializer):
    user_display_name = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = VideoProject
        fields = [
            'id', 'youtube_url', 'final_video_path', 'user_display_name',
            'image_style_preference', 'video_format_preference', 'created_at'
        ]

class VideoProjectSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoProject
        fields = [
            'scenes_data', 'image_style_preference', 'video_format_preference',
            'positive_style_keywords', 'negative_style_keywords', 'artist_influences'
        ]
        # Optional: Add validation for scenes_data structure if needed
        # def validate_scenes_data(self, value):
        #     if not isinstance(value, list):
        #         raise serializers.ValidationError("scenes_data must be a list.")
        #     for scene in value:
        #         if not all(k in scene for k in ('chunk_text', 'start_time', 'end_time', 'image_prompt')):
        #             raise serializers.ValidationError("Each scene is missing required keys.")
        #     return value
