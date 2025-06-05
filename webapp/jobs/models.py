from django.db import models
from django.conf import settings

class VideoProject(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('AWAITING_USER_INPUT', 'Awaiting User Input'),
        ('SPLITTING_SCENES', 'Splitting Scenes'),
        ('GENERATING_IMAGES', 'Generating Images'),
        ('COMPOSING_VIDEO', 'Composing Video'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed')
    ]
    IMAGE_STYLE_CHOICES = [
        ('default', 'Default (Modern Flat)'),
        ('photorealistic', 'Photorealistic'),
        ('cartoon', 'Cartoon / Comic'),
        ('abstract', 'Abstract'),
        ('pixel_art', 'Pixel Art'),
        ('line_art', 'Line Art'),
        ('fantasy', 'Fantasy Art'),
        ('anime', 'Anime / Manga Style')
    ]
    VIDEO_FORMAT_CHOICES = [
        ('9:16', 'Vertical Reel (9:16)'),
        ('16:9', 'Landscape Video (16:9)'),
        ('1:1', 'Square Post (1:1)')
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    youtube_url = models.URLField()
    duration_seconds = models.IntegerField()
    subtitle_preference = models.CharField(max_length=10, default='none')
    image_style_preference = models.CharField(max_length=50, choices=IMAGE_STYLE_CHOICES, default='default')
    video_format_preference = models.CharField(max_length=10, choices=VIDEO_FORMAT_CHOICES, default='9:16')

    # New fields for enhanced styling
    positive_style_keywords = models.TextField(blank=True, help_text='Comma-separated keywords to enhance style (e.g., vibrant, cinematic lighting)')
    negative_style_keywords = models.TextField(blank=True, help_text='Comma-separated keywords to avoid (e.g., blurry, text, watermark)')
    artist_influences = models.TextField(blank=True, help_text='Comma-separated artist names for style influence (e.g., Van Gogh, H.R. Giger)')

    is_public_in_gallery = models.BooleanField(default=False)
    celery_task_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    job_output_path_segment = models.CharField(max_length=255, blank=True, null=True)
    final_video_path = models.CharField(max_length=512, blank=True, null=True)
    transcript_path = models.CharField(max_length=512, blank=True, null=True)
    scenes_data = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Job {self.id} for {self.user.username} - Style: {self.image_style_preference}, Format: {self.video_format_preference}' # Updated str
    class Meta:
        ordering = ['-created_at']
