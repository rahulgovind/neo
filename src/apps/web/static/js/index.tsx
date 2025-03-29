import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './components';

// Import CSS styles
import '../css/message-fixes.css';

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('react-root');
  
  if (container) {
    // Hide the legacy content completely
    const legacyContent = document.getElementById('legacy-content');
    if (legacyContent) {
      legacyContent.style.display = 'none';
      legacyContent.innerHTML = ''; // Clear legacy content to avoid conflicts
    }
    
    // Make sure the react root is visible and takes full height
    container.style.display = 'block';
    container.style.minHeight = '100vh';
    
    // Initialize the React app
    const root = createRoot(container);
    root.render(<App />);
  } else {
    console.error('Could not find react-root element');
  }
});
