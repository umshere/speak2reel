from django.test import TestCase
from django.contrib.auth import get_user_model
from webapp.jobs.models import VideoProject

# User = get_user_model() # Should be CustomUser if configured in settings.AUTH_USER_MODEL
# For testing purposes, it's often easier to use the direct model if CustomUser is in another app,
# or ensure settings are configured for tests to use the correct User model.
# Let's assume settings.AUTH_USER_MODEL = 'users.CustomUser' is set for the project.
# If not, this might default to django.contrib.auth.models.User.
# For this placeholder, we'll use get_user_model() and it will resolve based on project settings.
User = get_user_model()

class VideoProjectModelTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser_jobs_model', password='password123')
        cls.video_project = VideoProject.objects.create(
            user=cls.user,
            youtube_url='http://example.com/video_jobs_model',
            duration_seconds=60,
            subtitle_preference='en',
            image_style_preference='cartoon',
            video_format_preference='16:9',
            # New style fields from Step 16
            positive_style_keywords='bright, cheerful',
            negative_style_keywords='dark, gloomy',
            artist_influences='Studio Ghibli'
        )

    def test_video_project_creation(self):
        project = VideoProject.objects.get(id=self.video_project.id)
        self.assertEqual(project.youtube_url, 'http://example.com/video_jobs_model')
        self.assertEqual(project.user.username, 'testuser_jobs_model')
        self.assertEqual(project.status, 'PENDING') # Default status
        self.assertEqual(project.image_style_preference, 'cartoon')
        self.assertEqual(project.video_format_preference, '16:9')
        self.assertEqual(project.positive_style_keywords, 'bright, cheerful')
        self.assertTrue(str(project).startswith('Job'))
        # Example of checking the __str__ output more precisely if needed:
        # expected_str = f'Job {project.id} for {project.user.username} ({project.status}) - Format: {project.video_format_preference}'
        # self.assertEqual(str(project), expected_str)


    def test_status_choices_update(self):
        project = VideoProject.objects.get(id=self.video_project.id)
        project.status = 'COMPLETED'
        project.save()
        updated_project = VideoProject.objects.get(id=project.id)
        self.assertEqual(updated_project.status, 'COMPLETED')

    def test_default_values(self):
        project = VideoProject.objects.create(
            user=self.user,
            youtube_url='http://another.com/video',
            duration_seconds=30
        )
        self.assertEqual(project.subtitle_preference, 'none') # Default from model
        self.assertEqual(project.image_style_preference, 'default') # Default from model
        self.assertEqual(project.video_format_preference, '9:16') # Default from model
        self.assertEqual(project.status, 'PENDING') # Default from model
        self.assertEqual(project.is_public_in_gallery, False) # Default from model
        self.assertEqual(project.positive_style_keywords, '') # Default blank
        self.assertEqual(project.negative_style_keywords, '') # Default blank
        self.assertEqual(project.artist_influences, '') # Default blank

    def test_json_field_scenes_data(self):
        project = VideoProject.objects.get(id=self.video_project.id)
        sample_scenes = [
            {'text': 'Scene 1', 'start': 0, 'end': 5, 'prompt': 'Prompt 1'},
            {'text': 'Scene 2', 'start': 5, 'end': 10, 'prompt': 'Prompt 2'}
        ]
        project.scenes_data = sample_scenes
        project.save()
        retrieved_project = VideoProject.objects.get(id=project.id)
        self.assertEqual(len(retrieved_project.scenes_data), 2)
        self.assertEqual(retrieved_project.scenes_data[0]['prompt'], 'Prompt 1')
