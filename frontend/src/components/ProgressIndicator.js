import React from 'react';

const ProgressIndicator = ({ progress, isVisible }) => {
  if (!isVisible || !progress) {
    return null;
  }

  const stages = [
    { key: 'uploading', label: 'Uploading', icon: '📤' },
    { key: 'extracting', label: 'Extracting', icon: '📄' },
    { key: 'chunking', label: 'Chunking', icon: '✂️' },
    { key: 'embedding', label: 'Embedding', icon: '🧠' },
    { key: 'indexing', label: 'Indexing', icon: '🗂️' }
  ];

  const getStageStatus = (stageKey) => {
    const stage = progress.stages[stageKey];
    return stage ? stage.status : 'pending';
  };

  const getStageMessage = (stageKey) => {
    const stage = progress.stages[stageKey];
    return stage ? stage.message : '';
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  return (
    <div className="progress-overlay">
      <div className="progress-modal">
        <div className="progress-header">
          <h3>Processing Document</h3>
          <div className="progress-filename">{progress.filename}</div>
        </div>

        <div className="progress-bar-container">
          <div className="progress-bar">
            <div 
              className="progress-bar-fill"
              style={{ width: `${progress.progress_percentage}%` }}
            ></div>
          </div>
          <div className="progress-percentage">{progress.progress_percentage}%</div>
        </div>

        <div className="progress-stages">
          {stages.map((stage, index) => {
            const status = getStageStatus(stage.key);
            const message = getStageMessage(stage.key);
            const stageData = progress.stages[stage.key];
            
            return (
              <div key={stage.key} className={`progress-stage ${status}`}>
                <div className="stage-icon">
                  {status === 'completed' ? '✅' : 
                   status === 'active' ? (
                     <div className="spinner-small"></div>
                   ) : 
                   status === 'failed' ? '❌' : 
                   stage.icon}
                </div>
                <div className="stage-content">
                  <div className="stage-label">{stage.label}</div>
                  <div className="stage-message">{message}</div>
                  {stageData && stageData.timestamp && (
                    <div className="stage-time">{formatTime(stageData.timestamp)}</div>
                  )}
                </div>
                <div className="stage-status">
                  {status === 'active' && <div className="pulse-dot"></div>}
                  {status === 'completed' && <div className="check-mark">✓</div>}
                  {status === 'failed' && <div className="error-mark">✗</div>}
                </div>
              </div>
            );
          })}
        </div>

        {progress.current_stage === 'completed' && (
          <div className="progress-success">
            <div className="success-icon">🎉</div>
            <div className="success-message">Document processed successfully!</div>
            <div className="processing-stats">
              {progress.processing_stats && (
                <>
                  <span>{progress.processing_stats.chunks_count} chunks created</span>
                  <span>{progress.processing_stats.embeddings_count} embeddings generated</span>
                </>
              )}
            </div>
          </div>
        )}

        {progress.current_stage === 'failed' && (
          <div className="progress-error">
            <div className="error-icon">❌</div>
            <div className="error-message">Processing failed</div>
            {progress.error_message && (
              <div className="error-details">{progress.error_message}</div>
            )}
          </div>
        )}

        {progress.started_at && (
          <div className="progress-footer">
            <div className="processing-time">
              Started: {formatTime(progress.started_at)}
              {progress.completed_at && (
                <> • Completed: {formatTime(progress.completed_at)}</>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProgressIndicator;
