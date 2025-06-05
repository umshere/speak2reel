import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import LandingPage from './LandingPage';
import axios from 'axios'; // Import to mock

// Mock axios globally for this test file
jest.mock('axios');

// Mock getCookie function if it's used by the component directly and not passed as prop
// If getCookie is defined inside LandingPage, it will be used unless component is refactored
// For simplicity, we assume getCookie is accessible or this test focuses on parts not needing it immediately.
// Or, mock it globally:
// jest.mock('./utils/cookies', () => ({ getCookie: jest.fn().mockReturnValue('test-csrf-token')}));

// Mock child components if they are complex and not the focus of these tests
jest.mock('./../../components/DashboardPage/DashboardPage', () => () => <div>Mocked Dashboard Page</div>);
jest.mock('./../../components/GalleryPage/GalleryPage', () => () => <div>Mocked Gallery Page</div>);


describe('LandingPage Component', () => {
  // Helper function to provide default props including navigateTo mock
  const renderLandingPage = (props = {}) => {
    const defaultProps = {
      navigateTo: jest.fn(), // Mock navigateTo passed from App.js
      // ... any other props LandingPage might expect from App.js
    };
    return render(<LandingPage {...defaultProps} {...props} />);
  };

  beforeEach(() => {
    // Reset any mock calls or implementations before each test
    axios.post.mockReset();
    axios.get.mockReset();
    // Mock successful getCookie by default for most tests
    // This is a global mock if getCookie is a global function or imported.
    // If defined inside LandingPage, this won't work directly.
    // For now, assume it's handled or not critical for all tests.
    global.getCookie = jest.fn().mockReturnValue('test-csrf-token');
  });


  test('renders hero section title and form elements', () => {
    renderLandingPage();
    expect(screen.getByText(/Transform Your Podcasts into Engaging Video Reels/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Enter YouTube Video URL/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Desired Video Format:/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Subtitle Preference:/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Generate Scenes!/i })).toBeInTheDocument();
  });

  test('allows typing in YouTube URL field', () => {
    renderLandingPage();
    const urlInput = screen.getByPlaceholderText(/Enter YouTube Video URL/i);
    fireEvent.change(urlInput, { target: { value: 'http://youtube.com/myvideo' } });
    expect(urlInput.value).toBe('http://youtube.com/myvideo');
  });

  test('job submission success shows success feedback and status button', async () => {
    axios.post.mockResolvedValueOnce({
      data: {
        job_id: 'celery123',
        video_project_id: 1,
        message: 'Job submitted'
      }
    });
    // Mock the subsequent status check call if handleJobSubmit triggers it
    axios.get.mockResolvedValueOnce({
        data: { db_status: 'PENDING', celery_status: 'PENDING', job_id: 'celery123', video_project_id: 1 }
    });


    renderLandingPage();
    const urlInput = screen.getByPlaceholderText(/Enter YouTube Video URL/i);
    const submitButton = screen.getByRole('button', { name: /Generate Scenes!/i });

    fireEvent.change(urlInput, { target: { value: 'http://youtube.com/validvideo' } });
    fireEvent.click(submitButton);

    expect(axios.post).toHaveBeenCalledTimes(1);
    // Check payload (optional, but good)
    expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/submit_job/',
        expect.objectContaining({ youtube_url: 'http://youtube.com/validvideo' }),
        expect.any(Object) // For headers and withCredentials
    );

    await waitFor(() => {
      expect(screen.getByText(/Job celery123 submitted!/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /Refresh Status for celery123/i})).toBeInTheDocument();
  });

  test('job submission failure shows error feedback', async () => {
    axios.post.mockRejectedValueOnce({
      response: { data: { detail: 'Invalid URL or server error' } }
    });
    renderLandingPage();
    fireEvent.change(screen.getByPlaceholderText(/Enter YouTube Video URL/i), { target: { value: 'http://youtube.com/invalidvideo' } });
    fireEvent.click(screen.getByRole('button', { name: /Generate Scenes!/i }));

    await waitFor(() => {
      // Check for the toast message related to submission error
      expect(screen.getByText(/Error submitting job: Invalid URL or server error/i)).toBeInTheDocument();
    });
  });

  test('job status check shows status and scene previews if available', async () => {
    const mockJobStatus = {
      video_project_id: 1, celery_task_id: 'celery123', db_status: 'AWAITING_USER_INPUT',
      scenes_data: [
        { chunk_text: 'Scene 1 text', start_time: 0, end_time: 5, image_prompt: 'Prompt for S1' },
        { chunk_text: 'Scene 2 text', start_time: 5, end_time: 10, image_prompt: 'Prompt for S2' },
      ],
      image_style_preference: 'cartoon', video_format_preference: '16:9',
      positive_style_keywords: 'vibrant', negative_style_keywords: '', artist_influences: ''
    };
    axios.get.mockResolvedValueOnce({ data: mockJobStatus });

    renderLandingPage();
    const jobIdInput = screen.getByPlaceholderText(/Enter Job ID/i);
    const getStatusButton = screen.getByRole('button', { name: /Get Status/i });

    fireEvent.change(jobIdInput, { target: { value: 'celery123' } });
    fireEvent.click(getStatusButton);

    await waitFor(() => {
      expect(screen.getByText(/Status for Job: celery123/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/DB Status: AWAITING_USER_INPUT/i)).toBeInTheDocument();
    expect(screen.getByText('Scene 1 text')).toBeInTheDocument(); // Check if scene text rendered
    expect(screen.getByDisplayValue('Prompt for S1')).toBeInTheDocument(); // Check if prompt in textarea
    // Check if style keywords textareas are populated
    expect(screen.getByDisplayValue('vibrant')).toBeInTheDocument();
  });

  test('saving updated settings (prompts and style) success', async () => {
    // Initial status load with scenes
    const initialJobStatus = {
      video_project_id: 1, celery_task_id: 'celery123', db_status: 'AWAITING_USER_INPUT',
      scenes_data: [{ chunk_text: 'S1', start_time: 0, end_time: 5, image_prompt: 'Old Prompt S1' }],
      image_style_preference: 'default', video_format_preference: '9:16',
      positive_style_keywords: '', negative_style_keywords: '', artist_influences: ''
    };
    axios.get.mockResolvedValueOnce({ data: initialJobStatus }); // For initial status load

    // Mock for the settings update POST call
    axios.post.mockResolvedValueOnce({
        data: {
            message: 'Settings saved!',
            // Backend should return the updated settings data
            data: {
                ...initialJobStatus, // or just the parts that can be updated
                scenes_data: [{ chunk_text: 'S1', start_time: 0, end_time: 5, image_prompt: 'New Prompt S1' }],
                image_style_preference: 'cartoon',
            }
        }
    });

    renderLandingPage();
    // Trigger initial status load
    fireEvent.change(screen.getByPlaceholderText(/Enter Job ID/i), { target: { value: 'celery123' } });
    fireEvent.click(screen.getByRole('button', { name: /Get Status/i }));

    await waitFor(() => screen.getByText('Save All Settings')); // Wait for save button to appear

    // Simulate editing a prompt
    const promptTextarea = await screen.findByDisplayValue('Old Prompt S1');
    fireEvent.change(promptTextarea, { target: { value: 'New Prompt S1' } });
    fireEvent.blur(promptTextarea); // Trigger onBlur to update parent state

    // Simulate changing image style
    const imageStyleSelect = screen.getByLabelText('Image Style:');
    fireEvent.change(imageStyleSelect, { target: { value: 'cartoon' } });

    // Click save settings
    const saveSettingsButton = screen.getByRole('button', { name: 'Save All Settings' });
    fireEvent.click(saveSettingsButton);

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/videoprojects/1/settings/', // Ensure this matches the URL construction
        expect.objectContaining({
          scenes_data: expect.arrayContaining([
            expect.objectContaining({ image_prompt: 'New Prompt S1' })
          ]),
          image_style_preference: 'cartoon'
        }),
        expect.any(Object)
      );
    });
    // Check for success toast
    expect(await screen.findByText(/Settings saved successfully!/i)).toBeInTheDocument();
  });

  // Test for "Proceed to Generate Images & Video" button (conceptual for now)
  test('proceed to generate images button shows info toast', async () => {
    const initialJobStatus = {
      video_project_id: 1, celery_task_id: 'celery123', db_status: 'AWAITING_USER_INPUT',
      scenes_data: [{ chunk_text: 'S1', start_time: 0, end_time: 5, image_prompt: 'Prompt S1' }],
    };
    axios.get.mockResolvedValueOnce({ data: initialJobStatus });

    renderLandingPage();
    fireEvent.change(screen.getByPlaceholderText(/Enter Job ID/i), { target: { value: 'celery123' } });
    fireEvent.click(screen.getByRole('button', { name: /Get Status/i }));

    const proceedButton = await screen.findByRole('button', { name: /Generate Images & Video with Saved Settings/i });
    fireEvent.click(proceedButton);

    expect(await screen.findByText(/Triggering image generation & video composition... \(Conceptual\)/i)).toBeInTheDocument();
  });

});
