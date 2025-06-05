import React, { useState, useEffect } from 'react';
import './App.css';
import LandingPage from './components/LandingPage/LandingPage';
import DashboardPage from './components/DashboardPage/DashboardPage';
import GalleryPage from './components/GalleryPage/GalleryPage'; // New component

function App() {
  const [currentPage, setCurrentPage] = useState('landing');

  const navigateTo = (page, stateData = {}) => { // Allow passing state
    setCurrentPage(page);
    const path = page === 'landing' ? '/' : `/${page}`;
    // Pass stateData along with history pushState
    window.history.pushState({page: page, ...stateData}, page, path);
  };

  useEffect(() => {
    const handlePopState = (event) => {
      const page = event.state ? event.state.page : 'landing';
      setCurrentPage(page);
      // Potentially pass other state from event.state if needed by components
    };
    window.addEventListener('popstate', handlePopState);

    const path = window.location.pathname.substring(1);
    if (path === 'dashboard' || path === 'gallery') {
      setCurrentPage(path);
    } else {
      setCurrentPage('landing');
    }
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);


  return (
    <div className='App'>
      <nav className='main-nav'>
        <button onClick={() => navigateTo('landing')}>Home</button>
        <button onClick={() => navigateTo('dashboard')}>My Dashboard</button>
        <button onClick={() => navigateTo('gallery')}>Community Gallery</button>
      </nav>
      {currentPage === 'landing' && <LandingPage navigateTo={navigateTo} />}
      {currentPage === 'dashboard' && <DashboardPage navigateTo={navigateTo} />}
      {currentPage === 'gallery' && <GalleryPage navigateTo={navigateTo} />}
    </div>
  );
}
export default App;
