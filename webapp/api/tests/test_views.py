from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from webapp.jobs.models import VideoProject # For creating test data
from unittest.mock import patch # For mocking Celery tasks

User = get_user_model()

class UserVideoProjectListViewTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user1 = User.objects.create_user(username='user1_api_list', password='password123')
        cls.user2 = User.objects.create_user(username='user2_api_list', password='password123')
        VideoProject.objects.create(user=cls.user1, youtube_url='http://u1.com/v1', duration_seconds=60)
        VideoProject.objects.create(user=cls.user1, youtube_url='http://u1.com/v2', duration_seconds=30)
        VideoProject.objects.create(user=cls.user2, youtube_url='http://u2.com/v1', duration_seconds=45)

    def test_list_projects_authenticated_user(self):
        self.client.login(username='user1_api_list', password='password123')
        url = reverse('user_video_project_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # DRF ListAPIView by default paginates. If not paginated, response.data is the list.
        # If paginated, response.data['results'] is the list.
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['youtube_url'], 'http://u1.com/v2') # Ordered by -created_at

    def test_list_projects_unauthenticated(self):
        url = reverse('user_video_project_list')
        response = self.client.get(url)
        # Default is 403 Forbidden if IsAuthenticated is used and no auth provided
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SubmitVideoJobViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testsubmituser_api', password='password')
        self.client = APIClient() # Use APIClient for DRF tests
        self.client.login(username='testsubmituser_api', password='password')
        self.submit_url = reverse('submit_video_job')
        self.valid_payload = {
            'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'duration': 30,
            'subtitles': 'none',
            'video_format': '9:16'
        }

    @patch('webapp.api.tasks.process_video_pipeline_task.delay') # Path to where .delay is called
    def test_submit_job_success(self, mock_celery_task_delay):
        # Mock the Celery task's .delay() method
        mock_celery_task_delay.return_value.id = 'test_celery_task_id_123' # Mock Celery task ID

        response = self.client.post(self.submit_url, self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('job_id', response.data) # Celery task ID
        self.assertEqual(response.data['job_id'], 'test_celery_task_id_123')
        self.assertIn('video_project_id', response.data) # DB PK

        # Verify a VideoProject was created in DB
        video_project_db_id = response.data['video_project_id']
        project_exists = VideoProject.objects.filter(id=video_project_db_id).exists()
        self.assertTrue(project_exists)

        # Verify Celery task was called
        mock_celery_task_delay.assert_called_once()
        # You can also check call arguments if needed:
        # args, kwargs = mock_celery_task_delay.call_args
        # self.assertEqual(kwargs['video_project_id'], video_project_db_id)


    def test_submit_job_invalid_payload_missing_url(self):
        payload = {**self.valid_payload}
        del payload['youtube_url']
        response = self.client.post(self.submit_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('youtube_url', response.data) # Check for error message on this field

    def test_submit_job_unauthenticated(self):
        self.client.logout() # Ensure client is not authenticated
        response = self.client.post(self.submit_url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# Placeholder for JobStatusView tests
class JobStatusViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='statususer', password='password')
        self.project = VideoProject.objects.create(
            user=self.user,
            youtube_url='http://status.com/test',
            duration_seconds=60,
            celery_task_id='celery_task_for_status_test'
        )
        self.client.login(username='statususer', password='password')
        self.status_url = reverse('job_status', kwargs={'job_id': self.project.celery_task_id})

    @patch('webapp.api.views.AsyncResult') # Mock Celery's AsyncResult
    def test_get_job_status_success(self, MockAsyncResult):
        # Configure the mock AsyncResult instance
        mock_task_result_instance = MockAsyncResult.return_value
        mock_task_result_instance.status = 'PROCESSING'
        mock_task_result_instance.result = None
        mock_task_result_instance.successful.return_value = False
        mock_task_result_instance.failed.return_value = False

        response = self.client.get(self.status_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['video_project_id'], self.project.id)
        self.assertEqual(response.data['celery_task_id'], self.project.celery_task_id)
        self.assertEqual(response.data['db_status'], 'PENDING') # Initial status from model
        self.assertEqual(response.data['celery_status'], 'PROCESSING')
        MockAsyncResult.assert_called_once_with(self.project.celery_task_id)

    def test_get_job_status_not_found(self):
        non_existent_url = reverse('job_status', kwargs={'job_id': 'non_existent_task_id'})
        response = self.client.get(non_existent_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

# Add more test classes for UpdateProjectSettingsView, ToggleProjectGalleryStatusView, PublicGalleryListView
# Example for UpdateProjectSettingsView
class UpdateProjectSettingsViewTest(APITestCase):
    # ... setUp with a user and a VideoProject instance ...
    def test_update_settings_success(self):
        # ... login user, construct URL with project PK ...
        # ... define valid payload with scenes_data, image_style_preference etc. ...
        # response = self.client.post(url, payload, format='json')
        # self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertEqual(response.data['data']['image_style_preference'], 'new_style')
        # updated_project = VideoProject.objects.get(pk=self.project.pk)
        # self.assertEqual(updated_project.image_style_preference, 'new_style')
        pass

# Test for PublicGalleryListView (no auth needed)
class PublicGalleryListViewTest(APITestCase):
    # ... setUpTestData with some COMPLETED and is_public_in_gallery=True projects ...
    def test_list_public_gallery_items(self):
        # url = reverse('public_gallery_list')
        # response = self.client.get(url)
        # self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertEqual(len(response.data.get('results', response.data)), /* number of public projects */)
        pass
