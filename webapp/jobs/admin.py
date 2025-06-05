from django.contrib import admin
from .models import VideoProject

@admin.register(VideoProject)
class VideoProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'youtube_url', 'status', 'celery_task_id', 'created_at', 'updated_at')
    list_filter = ('status', 'user')
    search_fields = ('youtube_url', 'user__username', 'celery_task_id')
    readonly_fields = ('created_at', 'updated_at', 'celery_task_id') # celery_task_id set by system
