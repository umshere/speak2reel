import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './DashboardPage.css';

// Re-use getCookie if needed for authenticated requests
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


const DashboardPage = ({ navigateTo }) => {
  const [projects, setProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isTogglingGallery, setIsTogglingGallery] = useState(null);

  const fetchProjects = useCallback(async () => {
    setIsLoading(true); setError(null); const csrftoken = getCookie('csrftoken');
    try {
      const response = await axios.get('/api/v1/user/projects/', {
          headers: { 'X-CSRFToken': csrftoken },
          withCredentials: true
      });
      setProjects(response.data.results || response.data);
    } catch (err) {
      console.error("Error fetching projects:", err);
      const errorMsg = err.response ? JSON.stringify(err.response.data) : 'Failed to fetch projects. Are you logged in?';
      setError({ message: errorMsg, status: err.response?.status });
      if (err.response && err.response.status === 403) {
          if (navigateTo) navigateTo('landing');
      }
    }
    finally { setIsLoading(false); }
  }, [navigateTo]);


  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleToggleGalleryStatus = async (projectId) => {
    setIsTogglingGallery(projectId);
    const csrftoken = getCookie('csrftoken');
    try {
      await axios.post(`/api/v1/videoprojects/${projectId}/toggle_gallery/`, {}, {
        headers: { 'X-CSRFToken': csrftoken },
        withCredentials: true
      });
      fetchProjects(); // Refresh projects list to show updated status
      alert('Project gallery status updated!'); // Replace with toast in a real app
    } catch (err) {
      alert('Failed to update gallery status: ' + (err.response?.data?.error || 'Unknown error'));
    } finally {
      setIsTogglingGallery(null);
    }
  };


  if (isLoading) return <div className='loading-indicator dashboard-loading'>Loading projects...</div>;
  if (error) return <div className='api-feedback error dashboard-error'>Error fetching projects: {error.message} (Status: {error.status})</div>;

  return (
    <div className='dashboard-page'>
      <h2>My Video Projects Dashboard</h2>
      {projects.length === 0 ? (
        <p>You haven't created any video projects yet.
           <button className='link-button' onClick={() => navigateTo ? navigateTo('landing') : window.location.href='/'}>
             Create one now!
           </button>
        </p>
      ) : (
        <table className='projects-table'>
          <thead>
            <tr>
              <th>ID</th>
              <th>YouTube URL</th>
              <th>Status</th>
              <th>Public</th>
              <th>Style</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {projects.map(project => (
              <tr key={project.id}>
                <td>{project.id}</td>
                <td><a href={project.youtube_url} target='_blank' rel='noopener noreferrer'>{project.youtube_url.substring(0,30)}...</a></td>
                <td><span className={`status-badge status-${project.status?.toLowerCase().replace(/\s+/g, '_')}`}>{project.status}</span></td>
                <td>{project.is_public_in_gallery ? 'Yes' : 'No'}</td>
                <td>{project.image_style_preference}</td>
                <td>{new Date(project.created_at).toLocaleDateString()}</td>
                <td>
                  <button
                    className='action-button'
                    onClick={() => {
                        alert(`To check status for Celery Task ID: ${project.celery_task_id}, please use the status checker on the Home page by copying this ID.`);
                        if(navigateTo) navigateTo('landing', { prefillJobId: project.celery_task_id });
                    }}
                    title='Check detailed status on Home page'
                    disabled={!project.celery_task_id}
                  >
                    Status
                  </button>
                  {project.status === 'COMPLETED' && project.final_video_path && (
                    <a href={`/media_placeholder/${project.final_video_path}`} target='_blank' rel='noopener noreferrer' className='action-button download-button'>
                      View
                    </a>
                  )}
                  {project.status === 'COMPLETED' && (
                    <button
                      className={`action-button ${project.is_public_in_gallery ? 'remove-gallery' : 'add-gallery'}`}
                      onClick={() => handleToggleGalleryStatus(project.id)}
                      disabled={isTogglingGallery === project.id}
                      title={project.is_public_in_gallery ? 'Remove from Community Gallery' : 'Share to Community Gallery'}
                    >
                      {isTogglingGallery === project.id
                        ? 'Updating...'
                        : (project.is_public_in_gallery ? 'Unshare' : 'Share')}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};
export default DashboardPage;
