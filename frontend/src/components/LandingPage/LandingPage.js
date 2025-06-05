import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './LandingPage.css';

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

const IMAGE_STYLE_CHOICES = [
    { key: 'default', label: 'Default (Modern Flat)' }, { key: 'photorealistic', label: 'Photorealistic' },
    { key: 'cartoon', label: 'Cartoon / Comic' }, { key: 'abstract', label: 'Abstract' },
    { key: 'pixel_art', label: 'Pixel Art' }, { key: 'line_art', label: 'Line Art' },
    { key: 'fantasy', label: 'Fantasy Art' }, { key: 'anime', label: 'Anime / Manga Style' },
];
const VIDEO_FORMAT_CHOICES = [
    { key: '9:16', label: 'Vertical Reel (9:16)' }, { key: '16:9', label: 'Landscape Video (16:9)' },
    { key: '1:1', label: 'Square Post (1:1)' },
];

const ToastNotification = ({ message, type, onClose }) => {
  if (!message) return null;
  useEffect(() => {
    const timer = setTimeout(() => onClose(), 5000);
    return () => clearTimeout(timer);
  }, [message, onClose]);
  return (
    <div className={`toast-notification toast-${type}`}>
      <span>{message}</span><button onClick={onClose} className='toast-close-btn'>&times;</button>
    </div>
  );
};

const ScenePreview = ({ scene, index, onPromptChange }) => {
  const [editablePrompt, setEditablePrompt] = useState(scene.image_prompt);
  const handleChange = (e) => setEditablePrompt(e.target.value);
  const handleBlur = () => { if (editablePrompt !== scene.image_prompt) onPromptChange(index, editablePrompt); };
  useEffect(() => { setEditablePrompt(scene.image_prompt); }, [scene.image_prompt]);

  return (
    <div className='scene-preview-item'>
      <h4>Scene {index + 1}</h4>
      <p><strong>Time:</strong> {scene.start_time?.toFixed(2)}s - {scene.end_time?.toFixed(2)}s</p>
      <p><strong>Text:</strong> {scene.chunk_text}</p>
      <div><strong>Prompt:</strong></div>
      <textarea value={editablePrompt || ''} onChange={handleChange} onBlur={handleBlur} rows='3'
                style={{ width: '95%', padding: '5px', marginTop: '5px', borderColor: editablePrompt !== scene.image_prompt ? 'orange' : '#ccc' }} />
      <div className='image-placeholder'>Image for scene {index + 1} (placeholder)</div>
    </div>
  );
};

const LandingPage = ({ navigateTo }) => {
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [subtitles, setSubtitles] = useState('none');
  const [videoFormat, setVideoFormat] = useState('9:16');
  const [apiResponse, setApiResponse] = useState(null);
  const [apiError, setApiError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [jobIdToCheck, setJobIdToCheck] = useState('');
  const [jobStatus, setJobStatus] = useState(null);
  const [jobStatusError, setJobStatusError] = useState(null);
  const [isCheckingStatus, setIsCheckingStatus] = useState(false);
  const [lastSubmittedJobId, setLastSubmittedJobId] = useState(null);
  const [editableScenesData, setEditableScenesData] = useState([]);
  const [selectedImageStyle, setSelectedImageStyle] = useState('default');
  const [positiveKeywords, setPositiveKeywords] = useState('');
  const [negativeKeywords, setNegativeKeywords] = useState('');
  const [artistInfluences, setArtistInfluences] = useState('');
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [toast, setToast] = useState({ message: '', type: '', key: 0 });

  const showToast = (message, type = 'info') => setToast({ message, type, key: Date.now() });
  const closeToast = () => setToast({ message: '', type: '', key: 0 });

  useEffect(() => {
    if (jobStatus) {
      setEditableScenesData(jobStatus.scenes_data ? JSON.parse(JSON.stringify(jobStatus.scenes_data)) : []);
      setSelectedImageStyle(jobStatus.image_style_preference || 'default');
      setVideoFormat(jobStatus.video_format_preference || '9:16');
      setPositiveKeywords(jobStatus.positive_style_keywords || '');
      setNegativeKeywords(jobStatus.negative_style_keywords || '');
      setArtistInfluences(jobStatus.artist_influences || '');
    } else {
      setEditableScenesData([]); setSelectedImageStyle('default'); setVideoFormat('9:16');
      setPositiveKeywords(''); setNegativeKeywords(''); setArtistInfluences('');
    }
  }, [jobStatus]);

  const handlePromptChange = useCallback((sceneIndex, newPrompt) => {
    setEditableScenesData(currentScenes =>
      currentScenes.map((scene, index) =>
        index === sceneIndex ? { ...scene, image_prompt: newPrompt } : scene
      )
    );
  }, []);

  const handleSaveSettings = async () => {
    if (!jobStatus || !jobStatus.video_project_id) { showToast('No job loaded to save settings for.', 'warning'); return; }
    setIsSavingSettings(true); closeToast();
    const csrftoken = getCookie('csrftoken');
    try {
      const payload = {
        scenes_data: editableScenesData,
        image_style_preference: selectedImageStyle,
        video_format_preference: videoFormat,
        positive_style_keywords: positiveKeywords,
        negative_style_keywords: negativeKeywords,
        artist_influences: artistInfluences
      };
      const response = await axios.post(
        `/api/v1/videoprojects/${jobStatus.video_project_id}/settings/`, // Updated URL
        payload,
        { headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken }, withCredentials: true }
      );
      // Update local jobStatus with the full response data which should be the updated project settings
      setJobStatus(prevStatus => ({ ...prevStatus, ...response.data.data, db_status: 'AWAITING_USER_INPUT' }));
      showToast('Settings saved successfully!', 'success');
    } catch (error) {
      showToast('Error saving settings: ' + (error.response?.data?.error || error.response?.data?.detail || error.message), 'error');
    } finally {
      setIsSavingSettings(false);
    }
  };

  const handleTriggerFullProcessing = async () => {
    if (!jobStatus || !jobStatus.video_project_id) { showToast('No job loaded.', 'warning'); return; }
    setIsLoading(true); closeToast();
    // const csrftoken = getCookie('csrftoken');
    showToast('Triggering image generation & video composition... (Conceptual - requires dedicated resume endpoint)', 'info');
    // Example:
    // try {
    //   await axios.post(`/api/v1/videoprojects/${jobStatus.video_project_id}/process_video/`, {},
    //     { headers: { 'X-CSRFToken': csrftoken }, withCredentials: true });
    //   showToast('Video processing re-triggered!', 'info');
    //   handleCheckJobStatus(null, jobStatus.celery_task_id || jobStatus.job_id); // Refresh status
    // } catch (error) { showToast('Error re-triggering processing.', 'error'); }
    setIsLoading(false); // Reset loading after conceptual call
  };

  const handleJobSubmit = async (event) => {
    event.preventDefault(); setIsLoading(true);
    setApiResponse(null); setApiError(null); setJobStatus(null); setJobStatusError(null); setLastSubmittedJobId(null); setEditableScenesData([]); closeToast();
    const csrftoken = getCookie('csrftoken');
    try {
      const response = await axios.post('/api/v1/submit_job/',
        { youtube_url: youtubeUrl, subtitles: subtitles, video_format: videoFormat, duration: 60 },
        { headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken }, withCredentials: true }
      );
      setApiResponse(response.data); setLastSubmittedJobId(response.data.job_id);
      showToast(`Job ${response.data.job_id} submitted.`, 'success');
      if (response.data.job_id) handleCheckJobStatus(null, response.data.job_id);
    } catch (error) {
        if (error.response) {
            setApiError(error.response.data);
            showToast('Error submitting job: ' + (error.response.data.detail || error.response.data.error || JSON.stringify(error.response.data)), 'error');
        } else if (error.request) {
            setApiError({ detail: 'No response from server.' });
            showToast('Error: No response from server.', 'error');
        } else {
            setApiError({ detail: 'Error: ' + error.message });
            showToast('Error: ' + error.message, 'error');
        }
    } finally { setIsLoading(false); }
  };

  const handleCheckJobStatus = async (event, jobId) => {
    if (event) event.preventDefault();
    const idToFetch = jobId || jobIdToCheck;
    if (!idToFetch) { showToast('Please enter Job ID.', 'warning'); return; }
    setIsCheckingStatus(true); setJobStatus(null); setJobStatusError(null); setEditableScenesData([]); closeToast();
    const csrftoken = getCookie('csrftoken');
    try {
      const response = await axios.get(`/api/v1/jobs/${idToFetch}/status/`, { headers: { 'X-CSRFToken': csrftoken }, withCredentials: true });
      setJobStatus(response.data);
      // Toast notifications based on status are now part of the main jobStatus display effect.
      if (response.data.db_status === 'COMPLETED') showToast(`Job ${idToFetch} COMPLETED!`, 'success');
      else if (response.data.db_status === 'FAILED') showToast(`Job ${idToFetch} FAILED.`, 'error');
      else showToast(`Status for ${idToFetch}: ${response.data.db_status}`, 'info');
    } catch (error) { /* ... error handling ... */ }
    finally { setIsCheckingStatus(false); }
  };

  useEffect(() => { if (lastSubmittedJobId) setJobIdToCheck(lastSubmittedJobId); }, [lastSubmittedJobId]);
  const handleCopyToClipboard = (text) => { /* ... */ };

  return (
    <div className='landing-page'>
      <ToastNotification key={toast.key} message={toast.message} type={toast.type} onClose={closeToast} />
      <header className='hero-section'>
        <h1>Create Engaging Video Content from Podcasts</h1>
        <form className='submission-form' onSubmit={handleJobSubmit}>
          <div className='form-group'>
            <input type='url' placeholder='Enter YouTube Video URL' className='url-input' value={youtubeUrl} onChange={(e) => setYoutubeUrl(e.target.value)} required />
          </div>
          <div className='form-group'>
            <label htmlFor='video-format-select'>Desired Video Format:</label>
            <select id='video-format-select' value={videoFormat} onChange={(e) => setVideoFormat(e.target.value)} className='subtitles-select'>
              {VIDEO_FORMAT_CHOICES.map(vf => (<option key={vf.key} value={vf.key}>{vf.label}</option>))}
            </select>
          </div>
          <div className='form-group'>
            <label htmlFor='subtitles-select'>Subtitle Preference:</label>
            <select id='subtitles-select' value={subtitles} onChange={(e) => setSubtitles(e.target.value)} className='subtitles-select'>
              <option value='none'>None</option><option value='orig'>Original</option><option value='en'>English</option><option value='both'>Both</option>
            </select>
          </div>
          <button type='submit' className='cta-button' disabled={isLoading}>{isLoading ? 'Submitting...' : 'Generate Scenes!'}</button>
        </form>
        {isLoading && <div className='loading-indicator'>Submitting job...</div>}
        {apiResponse && <div className='api-feedback success'>Job Submitted! Celery Task ID: {apiResponse.job_id} (DB ID: {apiResponse.video_project_id}) <button className='link-button' onClick={() => {setJobIdToCheck(apiResponse.job_id); handleCheckJobStatus(null, apiResponse.job_id);}}>Refresh Status</button></div>}
        {apiError && <div className='api-feedback error'><p>Submission Error:</p><pre>{JSON.stringify(apiError, null, 2)}</pre></div>}
      </header>

      <section className='job-status-section'>
        <h2>Check Job Status</h2>
        <form className='status-form' onSubmit={(e)=>handleCheckJobStatus(e, jobIdToCheck)}>
            <div className='form-group'><input type='text' placeholder='Enter Job ID' className='job-id-input' value={jobIdToCheck} onChange={(e) => setJobIdToCheck(e.target.value)} /></div>
            <button type='submit' className='cta-button secondary' disabled={isCheckingStatus}>{isCheckingStatus ? 'Checking...' : 'Get Status'}</button>
        </form>
        {isCheckingStatus && <div className='loading-indicator'>Checking status...</div>}
        {jobStatusError && <div className='api-feedback error'><p>Error Fetching Status:</p><pre>{JSON.stringify(jobStatusError, null, 2)}</pre></div>}

        {jobStatus && (
          <div className='api-feedback info job-details-container'>
            <h3>Job Details (DB ID: {jobStatus.video_project_id})</h3>
            <p><strong>Status:</strong> {jobStatus.db_status} {jobStatus.celery_status && `(Celery: ${jobStatus.celery_status})`}</p>
            <p><strong>Video Format:</strong> {VIDEO_FORMAT_CHOICES.find(f=>f.key === jobStatus.video_format_preference)?.label || jobStatus.video_format_preference}</p>
            <p><strong>Image Style:</strong> {IMAGE_STYLE_CHOICES.find(s=>s.key === jobStatus.image_style_preference)?.label || jobStatus.image_style_preference}</p>
            {jobStatus.error_message && <p><strong>Error:</strong> {jobStatus.error_message}</p>}

            {(jobStatus.db_status === 'COMPLETED' || jobStatus.celery_status === 'SUCCESS') && jobStatus.final_video_path && ( /* ... Share Buttons ... */ )}

            {jobStatus.scenes_data && jobStatus.scenes_data.length > 0 && (
              <div className='customization-section'>
                <h4>Review & Customize Settings:</h4>
                <div className='form-group'>
                  <label htmlFor='edit-video-format-select'>Video Format:</label>
                  <select id='edit-video-format-select' value={videoFormat} onChange={(e) => setVideoFormat(e.target.value)}
                          className='subtitles-select' style={{marginBottom: '10px'}}
                          disabled={!(jobStatus.db_status === 'PENDING' || jobStatus.db_status === 'AWAITING_USER_INPUT')}>
                    {VIDEO_FORMAT_CHOICES.map(vf => (<option key={vf.key} value={vf.key}>{vf.label}</option>))}
                  </select>
                </div>
                <div className='form-group'>
                  <label htmlFor='image-style-select'>Image Style:</label>
                  <select id='image-style-select' value={selectedImageStyle} onChange={(e) => setSelectedImageStyle(e.target.value)}
                          className='subtitles-select' style={{marginBottom: '10px'}}>
                    {IMAGE_STYLE_CHOICES.map(style => (<option key={style.key} value={style.key}>{style.label}</option>))}
                  </select>
                </div>
                <div className='form-group'>
                  <label htmlFor='positive-keywords'>Positive Keywords (comma-separated):</label>
                  <textarea id='positive-keywords' value={positiveKeywords} onChange={(e) => setPositiveKeywords(e.target.value)} rows='2' className='style-textarea'></textarea>
                </div>
                <div className='form-group'>
                  <label htmlFor='negative-keywords'>Negative Keywords (comma-separated):</label>
                  <textarea id='negative-keywords' value={negativeKeywords} onChange={(e) => setNegativeKeywords(e.target.value)} rows='2' className='style-textarea'></textarea>
                </div>
                <div className='form-group'>
                  <label htmlFor='artist-influences'>Artist Influences (comma-separated):</label>
                  <textarea id='artist-influences' value={artistInfluences} onChange={(e) => setArtistInfluences(e.target.value)} rows='2' className='style-textarea'></textarea>
                </div>
                <button onClick={handleSaveSettings} className='cta-button' style={{marginBottom: '10px'}} disabled={isSavingSettings}>
                  {isSavingSettings ? 'Saving...' : 'Save All Settings'}
                </button>
                {jobStatus.db_status === 'AWAITING_USER_INPUT' && (
                  <button onClick={handleTriggerFullProcessing} className='cta-button secondary' style={{marginLeft: '10px', marginBottom: '10px'}} disabled={isLoading}>
                    {isLoading ? 'Working...' : 'Proceed to Generate Images & Video'}
                  </button>
                )}
                <div className='scenes-preview-section'>
                  <h5>Scene Prompts (Editable):</h5>
                  <div className='scenes-grid'>
                    {editableScenesData.map((scene, index) => (
                      <ScenePreview key={index} scene={scene} index={index} onPromptChange={handlePromptChange} />
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </section>
      <footer className='landing-footer'><p>&copy; {new Date().getFullYear()} Podcast to Reels.</p></footer>
    </div>
  );
};
export default LandingPage;
