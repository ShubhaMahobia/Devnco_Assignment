import React, { useState, useRef } from 'react';
import { fileAPI } from '../services/api';
import SidebarProgressIndicator from './SidebarProgressIndicator';

const FileList = ({ files, selectedFile, onFileSelect, onFilesChange, loading }) => {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [message, setMessage] = useState(null);
  const [progress, setProgress] = useState(null);
  const [showProgress, setShowProgress] = useState(false);
  const fileInputRef = useRef(null);

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const handleFileUpload = async (file) => {
    if (!file) return;

    // Validate file type
    const allowedTypes = ['.pdf', '.docx', '.txt'];
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!allowedTypes.includes(fileExtension)) {
      setMessage({
        type: 'error',
        text: `File type ${fileExtension} is not supported. Please upload PDF, DOCX, or TXT files.`
      });
      return;
    }

    // Validate file size (50MB limit)
    const maxSize = 50 * 1024 * 1024; // 50MB in bytes
    if (file.size > maxSize) {
      setMessage({
        type: 'error',
        text: 'File size exceeds 50MB limit. Please choose a smaller file.'
      });
      return;
    }

    setUploading(true);
    setMessage(null);
    
    // Show immediate progress feedback
    setProgress({
      filename: file.name,
      current_stage: 'uploading',
      progress_percentage: 5,
      stages: {
        uploading: { status: 'active', message: 'Starting upload...', timestamp: new Date().toISOString() },
        extracting: { status: 'pending', message: 'Extracting text...', timestamp: null },
        chunking: { status: 'pending', message: 'Creating chunks...', timestamp: null },
        embedding: { status: 'pending', message: 'Generating embeddings...', timestamp: null },
        indexing: { status: 'pending', message: 'Indexing document...', timestamp: null }
      }
    });
    setShowProgress(true);

    try {
      // Start upload
      const uploadResponse = await fileAPI.uploadFile(file);
      const fileId = uploadResponse.file_id;

      // Connect to progress stream
      const eventSource = new EventSource(`http://127.0.0.1:8000/api/v1/files/progress/${fileId}`);
      
      eventSource.onmessage = (event) => {
        console.log('SSE Event received:', event);
        console.log('Event data:', event.data);
        
        try {
          const progressData = JSON.parse(event.data);
          console.log('Progress data:', progressData);
          setProgress(progressData);
          setShowProgress(true);
          
          // Close connection and hide progress when completed or failed
          if (progressData.current_stage === 'completed') {
            setTimeout(() => {
              setShowProgress(false);
              setProgress(null);
              eventSource.close();
              
              setMessage({
                type: 'success',
                text: `File "${file.name}" processed successfully!`
              });
              
              // Refresh file list
              onFilesChange();
              
              // Clear message after 5 seconds
              setTimeout(() => setMessage(null), 5000);
            }, 3000); // Show success for 3 seconds in sidebar
          } else if (progressData.current_stage === 'failed') {
            setTimeout(() => {
              setShowProgress(false);
              setProgress(null);
              eventSource.close();
              
              setMessage({
                type: 'error',
                text: progressData.error_message || 'Processing failed. Please try again.'
              });
            }, 3000); // Show error for 3 seconds
          }
        } catch (error) {
          console.error('Error parsing progress data:', error, 'Raw data:', event.data);
        }
      };

      eventSource.onerror = (error) => {
        console.error('Progress stream error:', error);
        eventSource.close();
        setShowProgress(false);
        setProgress(null);
        
        setMessage({
          type: 'error',
          text: 'Connection to progress stream failed. File may still be processing.'
        });
      };

    } catch (error) {
      console.error('Upload error:', error);
      setShowProgress(false);
      setProgress(null);
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to upload file. Please try again.'
      });
    } finally {
      setUploading(false);
    }
    
    // Fallback: If no SSE updates after 5 seconds, simulate progress
    setTimeout(() => {
      if (showProgress && progress && progress.current_stage === 'uploading') {
        console.log('No SSE updates received, simulating progress...');
        setProgress(prev => ({
          ...prev,
          current_stage: 'extracting',
          progress_percentage: 30,
          stages: {
            ...prev.stages,
            uploading: { ...prev.stages.uploading, status: 'completed' },
            extracting: { status: 'active', message: 'Extracting text from document...', timestamp: new Date().toISOString() }
          }
        }));
      }
    }, 5000);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    
    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      handleFileUpload(droppedFiles[0]);
    }
  };

  const handleFileInputChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      handleFileUpload(file);
    }
    // Reset input value so the same file can be selected again
    e.target.value = '';
  };

  const handleDeleteFile = async (fileId, fileName) => {
    if (!window.confirm(`Are you sure you want to delete "${fileName}"?`)) {
      return;
    }

    try {
      await fileAPI.deleteFile(fileId);
      setMessage({
        type: 'success',
        text: `File "${fileName}" deleted successfully!`
      });
      
      // Refresh file list
      onFilesChange();
      
      // Clear selection if deleted file was selected
      if (selectedFile && selectedFile.file_id === fileId) {
        onFileSelect(null);
      }
      
      // Clear message after 3 seconds
      setTimeout(() => setMessage(null), 3000);
    } catch (error) {
      console.error('Delete error:', error);
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to delete file. Please try again.'
      });
    }
  };

  return (
    <div className="sidebar">
        <div className="sidebar-header">
          <h2>Document Library</h2>
          <p>Upload and manage your documents</p>
        </div>

      {/* Upload Section */}
      <div className="upload-section">
        <div
          className={`upload-area ${dragOver ? 'dragover' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <div className="upload-icon">📁</div>
          <div className="upload-text">
            {uploading ? 'Uploading...' : 'Drag & drop files here'}
          </div>
          <div className="upload-subtext">
            or click to browse (PDF, DOCX, TXT)
          </div>
        </div>
        
        <input
          ref={fileInputRef}
          type="file"
          className="file-input"
          accept=".pdf,.docx,.txt"
          onChange={handleFileInputChange}
          disabled={uploading}
        />
        
        <button
          className="upload-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? 'Uploading...' : 'Choose File'}
        </button>
      </div>

      {/* Message Display */}
      {message && (
        <div className={`${message.type}-message`}>
          {message.text}
        </div>
      )}

      {/* File List */}
      <div className="file-list">
        <div className="file-list-header">
          Files ({files.length})
        </div>
        
        {loading ? (
          <div className="loading">
            <div className="loading-spinner"></div>
          </div>
        ) : files.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📄</div>
            <div className="empty-state-title">No files uploaded</div>
            <div className="empty-state-text">
              Upload your first document to get started
            </div>
          </div>
        ) : (
          files.map((file) => (
            <div
              key={file.file_id}
              className={`file-item ${selectedFile?.file_id === file.file_id ? 'selected' : ''}`}
              onClick={() => onFileSelect(file)}
            >
              <div className="file-name">{file.filename}</div>
              <div className="file-meta">
                <span className="file-size">{formatFileSize(file.file_size)}</span>
                <span className="file-date">{formatDate(file.upload_timestamp)}</span>
              </div>
              <div className="file-actions">
                <button
                  className="file-action-button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteFile(file.file_id, file.filename);
                  }}
                  title="Delete file"
                >
                  🗑️ Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>
      
      {/* Debug info */}
      {showProgress && (
        <div style={{ padding: '10px', background: 'yellow', margin: '10px', fontSize: '12px' }}>
          Debug: showProgress={showProgress.toString()}, hasProgress={!!progress}
          {progress && <div>Stage: {progress.current_stage}, %: {progress.progress_percentage}</div>}
        </div>
      )}
      
      {/* Sidebar Progress Indicator */}
      <SidebarProgressIndicator progress={progress} isVisible={showProgress} />
    </div>
  );
};

export default FileList;
