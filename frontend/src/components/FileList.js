import React, { useState, useRef } from 'react';
import { fileAPI } from '../services/api';

const FileList = ({ files, selectedFile, onFileSelect, onFilesChange, loading }) => {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [message, setMessage] = useState(null);
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

    try {
      await fileAPI.uploadFile(file);
      setMessage({
        type: 'success',
        text: `File "${file.name}" uploaded successfully!`
      });
      
      // Refresh file list
      onFilesChange();
      
      // Clear message after 3 seconds
      setTimeout(() => setMessage(null), 3000);
    } catch (error) {
      console.error('Upload error:', error);
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to upload file. Please try again.'
      });
    } finally {
      setUploading(false);
    }
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
    </div>
  );
};

export default FileList;
