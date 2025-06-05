import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './GalleryPage.css';

const GalleryItem = ({ project }) => {
  // Construct video URL. This assumes final_video_path is a relative path
  // from a common media root configured in Django.
  // For local dev, Django's dev server might serve media if configured.
  // For production, this would typically be a CDN URL or a direct link from cloud storage.
  // The '/media_placeholder/' is a conceptual base.
  const videoUrl = project.final_video_path
    ? (project.final_video_path.startsWith('http') ? project.final_video_path : `/media_placeholder/${project.final_video_path}`)
    : null;

  return (
    <div className='gallery-item'>
      {/* <h4>{project.title || 'Community Reel'}</h4> */}
      <p className='gallery-item-user'>Shared by: {project.user_display_name}</p>

      {videoUrl ? (
        <video controls width='100%' preload='metadata' className='gallery-video'>
          <source src={videoUrl} type='video/mp4' />
          Your browser does not support the video tag.
        </video>
      ) : (
        <div className='video-placeholder'>Video processing or not available.</div>
      )}

      <div className='gallery-item-details'>
        <p><strong>Style:</strong> {project.image_style_preference}</p>
        <p><a href={project.youtube_url} target='_blank' rel='noopener noreferrer'>Original Source</a></p>
        <p><small>Shared on: {new Date(project.created_at).toLocaleDateString()}</small></p>
      </div>
    </div>
  );
};

const GalleryPage = () => {
  const [publicProjects, setPublicProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPublicProjects = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await axios.get('/api/v1/gallery/');
        // Assuming DRF pagination, response.data might be {count, next, previous, results}
        // If not paginated, it's just the list.
        setPublicProjects(response.data.results || response.data);
      } catch (err) {
        console.error("Error fetching gallery projects:", err);
        setError(err.response ? err.response.data : 'Failed to fetch gallery projects.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchPublicProjects();
  }, []);

  if (isLoading) return <div className='loading-indicator gallery-loading'>Loading gallery...</div>;
  if (error) return <div className='api-feedback error gallery-error'>Error fetching gallery: {typeof error === 'string' ? error : JSON.stringify(error)}</div>;

  return (
    <div className='gallery-page'>
      <h2>Community Showcase Gallery</h2>
      <p className='gallery-intro'>Discover amazing video reels created by our community!</p>
      {publicProjects.length === 0 ? (
        <p className='gallery-empty'>No public projects shared yet. Why not be the first? Complete a project and share it from your dashboard!</p>
      ) : (
        <div className='gallery-grid'>
          {publicProjects.map(project => (
            <GalleryItem key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  );
};
export default GalleryPage;
