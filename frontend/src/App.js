import React, { useState, useEffect } from 'react';
import './App.css';
import FileList from './components/FileList';
import PDFViewer from './components/PDFViewer';
import { fileAPI, healthAPI } from './services/api';

function App() {
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [backendStatus, setBackendStatus] = useState(null);

  // Check backend health on startup
  useEffect(() => {
    checkBackendHealth();
  }, []);

  // Load files on startup
  useEffect(() => {
    loadFiles();
  }, []);

  const checkBackendHealth = async () => {
    try {
      const health = await healthAPI.checkHealth();
      setBackendStatus(health.status);
    } catch (error) {
      console.error('Backend health check failed:', error);
      setBackendStatus('unhealthy');
      setError('Cannot connect to backend server. Please ensure the server is running on http://127.0.0.1:8000');
    }
  };

  const loadFiles = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const fileList = await fileAPI.listFiles();
      setFiles(fileList);
    } catch (error) {
      console.error('Failed to load files:', error);
      setError('Failed to load files. Please check your connection.');
      setFiles([]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (file) => {
    setSelectedFile(file);
  };

  const handleFilesChange = () => {
    // Reload files when changes occur (upload/delete)
    loadFiles();
  };

  // Show connection error if backend is not available
  if (backendStatus === 'unhealthy') {
    return (
      <div className="App">
        <div className="empty-state" style={{ height: '100vh' }}>
          <div className="empty-state-icon">⚠️</div>
          <div className="empty-state-title">Backend Connection Error</div>
          <div className="empty-state-text">
            {error || 'Cannot connect to the backend server.'}
            <br /><br />
            Please ensure the backend server is running:
            <br />
            <code>cd backend && python start_server.py</code>
          </div>
          <button 
            className="upload-button" 
            onClick={checkBackendHealth}
            style={{ marginTop: '20px' }}
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="App">
      {/* Left Sidebar - File List */}
      <FileList
        files={files}
        selectedFile={selectedFile}
        onFileSelect={handleFileSelect}
        onFilesChange={handleFilesChange}
        loading={loading}
      />

      {/* Main Content - PDF Viewer */}
      <PDFViewer selectedFile={selectedFile} />
    </div>
  );
}

export default App;
