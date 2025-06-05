from django.urls import path
from .views import (
    SubmitVideoJobView,
    JobStatusView,
    UpdateProjectSettingsView, # Changed from UpdateScenePromptsView
    UserVideoProjectListView,
    ToggleProjectGalleryStatusView,
    PublicGalleryListView
)

urlpatterns = [
    path('submit_job/', SubmitVideoJobView.as_view(), name='submit_video_job'),
    path('jobs/<str:job_id>/status/', JobStatusView.as_view(), name='job_status'),
    # Path updated to reflect new view name and purpose
    path('videoprojects/<int:video_project_pk>/settings/', UpdateProjectSettingsView.as_view(), name='update_project_settings'),
    path('user/projects/', UserVideoProjectListView.as_view(), name='user_video_project_list'),
    path('videoprojects/<int:video_project_pk>/toggle_gallery/', ToggleProjectGalleryStatusView.as_view(), name='toggle_project_gallery_status'),
    path('gallery/', PublicGalleryListView.as_view(), name='public_gallery_list'),
]
