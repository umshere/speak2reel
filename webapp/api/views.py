from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .serializers import (
    VideoJobSubmitSerializer, VideoJobResponseSerializer,
    VideoProjectListSerializer, PublicVideoProjectSerializer,
    VideoProjectSettingsSerializer # New serializer for settings update
)
from webapp.jobs.models import VideoProject
from .tasks import process_video_pipeline_task
from celery.result import AsyncResult
import os

JOBS_BASE_OUTPUT_DIR = os.path.join(os.getcwd(), 'job_outputs')
os.makedirs(JOBS_BASE_OUTPUT_DIR, exist_ok=True)

class SubmitVideoJobView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        serializer = VideoJobSubmitSerializer(data=request.data)
        if serializer.is_valid():
            vd = serializer.validated_data
            try:
                video_project = VideoProject.objects.create(
                    user=request.user, youtube_url=vd['youtube_url'],
                    duration_seconds=vd['duration'], subtitle_preference=vd['subtitles'],
                    video_format_preference=vd['video_format'],
                    # New style fields will use model defaults or be blank
                    status='PENDING'
                )
            except Exception as e:
                print(f"Error creating VideoProject: {e}")
                return Response({'error': f'Failed to init job: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            try:
                task = process_video_pipeline_task.delay(
                    video_project_id=video_project.id,
                    youtube_url=video_project.youtube_url,
                    duration=video_project.duration_seconds,
                    subtitles=video_project.subtitle_preference,
                    video_format=video_project.video_format_preference,
                    output_dir_base=JOBS_BASE_OUTPUT_DIR,
                    initial_run=True
                )
                video_project.celery_task_id = task.id
                video_project.save()

                response_data = {
                    'job_id': task.id,
                    'video_project_id': video_project.id,
                    'message': 'Job submitted successfully. Initial processing started.',
                    'status_url': f'/api/v1/jobs/{task.id}/status/'
                }
                return Response(VideoJobResponseSerializer(response_data).data, status=status.HTTP_202_ACCEPTED)
            except Exception as e:
                video_project.status = 'FAILED'
                video_project.error_message = f'Failed to submit job to Celery: {str(e)}'
                video_project.save()
                print(f"Error submitting job to Celery: {e}")
                return Response({'error': f'Celery submit failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UpdateProjectSettingsView(APIView): # Renamed from UpdateScenePromptsView
    permission_classes = [IsAuthenticated]
    def post(self, request, video_project_pk, *args, **kwargs):
        video_project = get_object_or_404(VideoProject, pk=video_project_pk, user=request.user)

        serializer = VideoProjectSettingsSerializer(video_project, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save() # This saves all fields defined in VideoProjectSettingsSerializer

            # Update status logic based on what was saved
            if video_project.status in ['PENDING', 'AWAITING_USER_INPUT', 'SPLITTING_SCENES']: # Allow updates if not too far
                 video_project.status = 'AWAITING_USER_INPUT' # Ready for user to trigger next step
            # If only keywords were updated, and scenes_data already existed, status might remain AWAITING_USER_INPUT
            # Or set a new status like 'SETTINGS_UPDATED_AWAITING_PROCESSING'

            video_project.save() # Save any status change

            # Return all settings that can be edited on the client, using the same serializer
            # This ensures client has the latest full set of editable settings.
            return Response({
                'message': 'Project settings updated successfully.',
                'data': VideoProjectSettingsSerializer(video_project).data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class JobStatusView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, job_id, *args, **kwargs): # job_id is Celery Task ID
        video_project = get_object_or_404(VideoProject, celery_task_id=job_id, user=request.user)
        celery_status_info = {}
        if video_project.celery_task_id:
            task_result = AsyncResult(video_project.celery_task_id)
            celery_status_info = {
                'celery_status': task_result.status,
                'celery_result': task_result.result if task_result.successful() else (str(task_result.info) if task_result.failed() else None)
            }

        # Use VideoProjectSettingsSerializer for the editable parts, plus other read-only info
        settings_data = VideoProjectSettingsSerializer(video_project).data
        response_data = {
            'video_project_id': video_project.id,
            'celery_task_id': video_project.celery_task_id,
            'db_status': video_project.status,
            'youtube_url': video_project.youtube_url,
            'duration_seconds': video_project.duration_seconds,
            'subtitle_preference': video_project.subtitle_preference,
            'created_at': video_project.created_at.isoformat(),
            'updated_at': video_project.updated_at.isoformat(),
            'error_message': video_project.error_message,
            'final_video_path': video_project.final_video_path,
            'transcript_path': video_project.transcript_path,
            'is_public_in_gallery': video_project.is_public_in_gallery,
            **settings_data, # Includes scenes_data, image_style_preference, video_format_preference, and new keywords
            **celery_status_info
        }
        return Response(response_data)

class UserVideoProjectListView(ListAPIView):
    serializer_class = VideoProjectListSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return VideoProject.objects.filter(user=self.request.user).order_by('-created_at')

class ToggleProjectGalleryStatusView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, video_project_pk, *args, **kwargs):
        video_project = get_object_or_404(VideoProject, pk=video_project_pk, user=request.user)
        if video_project.status != 'COMPLETED':
            return Response({'error': 'Only completed projects can be shared.'}, status=status.HTTP_400_BAD_REQUEST)
        video_project.is_public_in_gallery = not video_project.is_public_in_gallery
        video_project.save()
        return Response({
            'message': f'Project gallery status: {"Public" if video_project.is_public_in_gallery else "Private"}.',
            'video_project_id': video_project.id,
            'is_public_in_gallery': video_project.is_public_in_gallery
        }, status=status.HTTP_200_OK)

class PublicGalleryListView(ListAPIView):
    serializer_class = PublicVideoProjectSerializer
    def get_queryset(self):
        return VideoProject.objects.filter(is_public_in_gallery=True, status='COMPLETED').order_by('-updated_at')
