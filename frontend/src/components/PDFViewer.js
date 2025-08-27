import React, { useState, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import ChatInterface from './ChatInterface';

// Set up PDF.js worker - use local worker from public directory
pdfjs.GlobalWorkerOptions.workerSrc = `${process.env.PUBLIC_URL}/pdf.worker.min.js`;

const PDFViewer = ({ selectedFile }) => {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const onDocumentLoadSuccess = useCallback(({ numPages }) => {
    setNumPages(numPages);
    setPageNumber(1);
    setLoading(false);
    setError(null);
  }, []);

  const onDocumentLoadError = useCallback((error) => {
    console.error('PDF load error:', error);
    setError('Failed to load PDF. The file might be corrupted or unsupported.');
    setLoading(false);
  }, []);

  const onDocumentLoadStart = useCallback(() => {
    setLoading(true);
    setError(null);
  }, []);

  const goToPrevPage = () => {
    setPageNumber(prev => Math.max(prev - 1, 1));
  };

  const goToNextPage = () => {
    setPageNumber(prev => Math.min(prev + 1, numPages || 1));
  };

  const goToPage = (page) => {
    const pageNum = parseInt(page, 10);
    if (pageNum >= 1 && pageNum <= numPages) {
      setPageNumber(pageNum);
    }
  };

  // Get file URL for PDF viewing
  const getFileUrl = () => {
    if (!selectedFile) return null;
    
    // For PDF files, we need to construct the download URL
    // This assumes your backend has a download endpoint
    return `http://127.0.0.1:8000/api/v1/files/${selectedFile.file_id}/download`;
  };

  const renderContent = () => {
    if (!selectedFile) {
      return (
        <div className="empty-state">
          <div className="empty-state-icon">📄</div>
          <div className="empty-state-title">No document selected</div>
          <div className="empty-state-text">
            Select a document from the sidebar to view it here
          </div>
        </div>
      );
    }

    // Check if file is PDF
    if (!selectedFile.content_type || !selectedFile.content_type.includes('pdf')) {
      return (
        <div className="empty-state">
          <div className="empty-state-icon">📄</div>
          <div className="empty-state-title">Preview not available</div>
          <div className="empty-state-text">
            PDF preview is only available for PDF files.<br/>
            Selected file: {selectedFile.filename}
          </div>
        </div>
      );
    }

    if (loading) {
      return (
        <div className="loading">
          <div className="loading-spinner"></div>
          <p>Loading PDF...</p>
        </div>
      );
    }

    if (error) {
      return (
        <div className="empty-state">
          <div className="empty-state-icon">❌</div>
          <div className="empty-state-title">Error loading PDF</div>
          <div className="empty-state-text">{error}</div>
        </div>
      );
    }

    return (
      <div className="pdf-viewer-container">
        {/* PDF Controls */}
        <div className="pdf-controls">
          <button
            className="pdf-control-button"
            onClick={goToPrevPage}
            disabled={pageNumber <= 1}
          >
            ← Previous
          </button>
          
          <div className="page-info">
            Page{' '}
            <input
              type="number"
              min="1"
              max={numPages || 1}
              value={pageNumber}
              onChange={(e) => goToPage(e.target.value)}
              style={{
                width: '60px',
                textAlign: 'center',
                padding: '4px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                margin: '0 8px'
              }}
            />
            of {numPages || '?'}
          </div>
          
          <button
            className="pdf-control-button"
            onClick={goToNextPage}
            disabled={pageNumber >= numPages}
          >
            Next →
          </button>
        </div>

        {/* PDF Document */}
        <div className="pdf-viewer">
          <Document
            file={getFileUrl()}
            onLoadStart={onDocumentLoadStart}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="loading">
                <div className="loading-spinner"></div>
              </div>
            }
            error={
              <div className="empty-state">
                <div className="empty-state-icon">❌</div>
                <div className="empty-state-title">Failed to load PDF</div>
                <div className="empty-state-text">
                  Please check if the file exists and is a valid PDF
                </div>
              </div>
            }
          >
            <Page
              pageNumber={pageNumber}
              scale={1.0}
              loading={
                <div className="loading">
                  <div className="loading-spinner"></div>
                </div>
              }
              error={
                <div className="empty-state">
                  <div className="empty-state-icon">❌</div>
                  <div className="empty-state-title">Failed to load page</div>
                </div>
              }
            />
          </Document>
        </div>
      </div>
    );
  };

  return (
    <div className="main-content">
      <div className="content-header">
        <h1 className="content-title">
          {selectedFile ? selectedFile.filename : 'Document Viewer'}
        </h1>
        <p className="content-subtitle">
          {selectedFile 
            ? `${selectedFile.content_type} • ${(selectedFile.file_size / 1024).toFixed(1)} KB`
            : 'Select a document to view'
          }
        </p>
      </div>
      
      {renderContent()}
      
      {/* Chat Interface below PDF viewer */}
      <ChatInterface selectedFile={selectedFile} />
    </div>
  );
};

export default PDFViewer;
