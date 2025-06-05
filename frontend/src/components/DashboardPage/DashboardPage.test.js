import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import DashboardPage from './DashboardPage';
import axios from 'axios';

jest.mock('axios');

// Mock getCookie globally for these tests
global.getCookie = jest.fn().mockReturnValue('test-csrf-token');

describe('DashboardPage Component', () => {
  const mockNavigateTo = jest.fn();

  beforeEach(() => {
    axios.get.mockReset();
    axios.post.mockReset(); // For gallery toggle
    mockNavigateTo.mockClear();
  });

  test('renders loading state initially', () => {
    axios.get.mockResolvedValueOnce({ data: [] });
    render(<DashboardPage navigateTo={mockNavigateTo} />);
    expect(screen.getByText(/Loading projects.../i)).toBeInTheDocument();
  });

  test('renders projects table after successful fetch', async () => {
    const mockProjects = [
      { id: 1, youtube_url: 'http://vid1.com', status: 'COMPLETED', image_style_preference: 'default', video_format_preference: '9:16', created_at: new Date().toISOString(), celery_task_id: 'task1', is_public_in_gallery: false, final_video_path: 'path/to/video1.mp4', duration_seconds: 60, subtitle_preference: 'en' },
      { id: 2, youtube_url: 'http://vid2.com', status: 'PENDING', image_style_preference: 'cartoon', video_format_preference: '16:9', created_at: new Date().toISOString(), celery_task_id: 'task2', is_public_in_gallery: true, duration_seconds: 30, subtitle_preference: 'none'  },
    ];
    // Simulate DRF paginated response or direct list
    axios.get.mockResolvedValueOnce({ data: { results: mockProjects } });

    render(<DashboardPage navigateTo={mockNavigateTo} />);

    await waitFor(() => {
      expect(screen.getByText(/http:\/\/vid1.com/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/http:\/\/vid2.com/i)).toBeInTheDocument();
    expect(screen.getByText('COMPLETED')).toBeInTheDocument();
    expect(screen.getByText('PENDING')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Status/i }).length).toBe(2);
    expect(screen.getByRole('link', { name: /View/i })).toBeInTheDocument(); // For vid1
    expect(screen.getByRole('button', { name: /Share to Gallery/i })).toBeInTheDocument(); // For vid1 (COMPLETED)
    expect(screen.getByRole('button', { name: /Unshare/i })).toBeInTheDocument(); // For vid2 (COMPLETED and public)
  });

  test('renders error message on fetch failure', async () => {
    axios.get.mockRejectedValueOnce({ response: { data: {detail: 'Server Error'}, status: 500 }});
    render(<DashboardPage navigateTo={mockNavigateTo} />);
    await waitFor(() => {
      expect(screen.getByText(/Error fetching projects: {"detail":"Server Error"} \(Status: 500\)/i)).toBeInTheDocument();
    });
  });

  test('renders "no projects" message if API returns empty list', async () => {
    axios.get.mockResolvedValueOnce({ data: { results: [] } });
    render(<DashboardPage navigateTo={mockNavigateTo} />);
    await waitFor(() => {
      expect(screen.getByText(/You haven't created any video projects yet/i)).toBeInTheDocument();
    });
  });

  test('handles "Share to Gallery" button click and updates UI', async () => {
    const mockProjectsInitial = [
      { id: 1, youtube_url: 'http://vid1.com', status: 'COMPLETED', is_public_in_gallery: false, celery_task_id: 'task1', created_at: new Date().toISOString(), final_video_path: 'path/to/video1.mp4' },
    ];
    const mockProjectsUpdated = [
      { ...mockProjectsInitial[0], is_public_in_gallery: true },
    ];
    axios.get.mockResolvedValueOnce({ data: { results: mockProjectsInitial } }); // Initial fetch
    axios.post.mockResolvedValueOnce({ data: { message: 'Status updated', is_public_in_gallery: true } }); // Toggle API call
    axios.get.mockResolvedValueOnce({ data: { results: mockProjectsUpdated } }); // Refetch

    render(<DashboardPage navigateTo={mockNavigateTo} />);

    const shareButton = await screen.findByRole('button', { name: /Share to Gallery/i });
    fireEvent.click(shareButton);

    expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/videoprojects/1/toggle_gallery/',
        {},
        expect.any(Object)
    );

    // Wait for the button text to change after refetch
    await waitFor(() => {
        expect(screen.getByRole('button', { name: /Unshare/i })).toBeInTheDocument();
    });
    // Also check if the "Public" column updated
    expect(screen.getByText('Yes')).toBeInTheDocument();
  });

  test('View Status button click navigates to landing page (conceptual)', async () => {
    const mockProjects = [
      { id: 1, youtube_url: 'http://vid1.com', status: 'COMPLETED', celery_task_id: 'task1', created_at: new Date().toISOString() },
    ];
    axios.get.mockResolvedValueOnce({ data: { results: mockProjects } });
    render(<DashboardPage navigateTo={mockNavigateTo} />);

    const statusButton = await screen.findByRole('button', { name: /Status/i });
    fireEvent.click(statusButton);

    expect(mockNavigateTo).toHaveBeenCalledWith('landing');
    // In a real test with routing, you'd also check if location changed or if
    // LandingPage received props to pre-fill job ID.
    // For now, the alert inside the component is not easily testable without more setup.
  });

});
