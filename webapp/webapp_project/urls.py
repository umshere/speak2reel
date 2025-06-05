from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

# Placeholder home view from previous step
def home_view(request):
    user_info = ''
    if request.user.is_authenticated:
        user_info = f'Logged in as {request.user.username}. <a href="/accounts/logout/">Logout</a>'
    else:
        user_info = '<a href="/accounts/login/">Login</a> or <a href="/accounts/register/">Register</a>'
    # Add a link to submit a job if authenticated
    if request.user.is_authenticated:
        user_info += '<br><a href="/api/v1/submit_job_page/">Submit New Video Job (Test Page)</a>' # Simple test page
    return HttpResponse(f'<h1>Welcome to Podcast to Reels!</h1><p>{user_info}</p>')

# Placeholder view for a test page to submit a job via a form (not a real frontend)
def submit_job_test_page_view(request):
    # This is a very basic HTML form for testing the API endpoint directly.
    # The real frontend would use JavaScript (e.g., React) to make an AJAX call.
    if not request.user.is_authenticated:
        return HttpResponse('Please login to submit a job.', status=403)

    form_html = """
    <h2>Test Submit Video Job</h2>
    <form id="jobForm" method="POST" action="/api/v1/submit_job/">
        <p>NOTE: This form submits directly to the API. In a real app, this would be a JavaScript call from React.</p>
        <div><label for="youtube_url">YouTube URL:</label>
        <input type="url" id="youtube_url" name="youtube_url" required></div>
        <div><label for="duration">Duration (seconds):</label>
        <input type="number" id="duration" name="duration" value="30"></div>
        <div><label for="subtitles">Subtitles:</label>
        <select id="subtitles" name="subtitles">
            <option value="none">None</option>
            <option value="orig">Original</option>
            <option value="en">English</option>
            <option value="both">Both</option>
        </select></div>
        <div id="csrf_token_placeholder"></div>
        <button type="button" onclick="submitApiForm()">Submit Job</button>
    </form>
    <div id="responseArea"></div>
    <script>
        // Function to get CSRF token from cookie (Django default)
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
        const csrftoken = getCookie('csrftoken');

        async function submitApiForm() {
            const form = document.getElementById('jobForm');
            const responseArea = document.getElementById('responseArea');
            responseArea.innerHTML = 'Submitting...';

            const formData = {
                youtube_url: document.getElementById('youtube_url').value,
                duration: parseInt(document.getElementById('duration').value),
                subtitles: document.getElementById('subtitles').value
            };

            try {
                const response = await fetch('/api/v1/submit_job/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrftoken
                    },
                    body: JSON.stringify(formData)
                });
                const data = await response.json();
                if (response.ok) {
                    responseArea.innerHTML = '<p>Success!</p><pre>' + JSON.stringify(data, null, 2) + '</pre>';
                    if(data.status_url) {
                        responseArea.innerHTML += '<p><a href="' + data.status_url + '" target="_blank">Check Status</a></p>';
                    }
                } else {
                    responseArea.innerHTML = '<p>Error!</p><pre>' + JSON.stringify(data, null, 2) + '</pre>';
                }
            } catch (error) {
                responseArea.innerHTML = '<p>Fetch Error!</p><pre>' + error.toString() + '</pre>';
            }
        }
    </script>
    """
    return HttpResponse(form_html)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('webapp.users.urls')),
    path('api/v1/', include('webapp.api.urls')), # Namespace for V1 API
    path('', home_view, name='home'),
    path('api/v1/submit_job_page/', submit_job_test_page_view, name='submit_job_test_page'), # Test page
]
