import React from 'react';

const SidebarProgressIndicator = ({ progress, isVisible }) => {
  console.log('SidebarProgressIndicator render:', { progress, isVisible });
  
  if (!isVisible || !progress) {
    console.log('SidebarProgressIndicator not rendering:', { isVisible, hasProgress: !!progress });
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

  const getCurrentStageMessage = () => {
    const currentStage = progress.stages[progress.current_stage];
    return currentStage ? currentStage.message : 'Processing...';
  };

  return (
    <div className="sidebar-progress">
      <div className="sidebar-progress-header">
        <div className="sidebar-progress-title">Processing File</div>
        <div className="sidebar-progress-filename">{progress.filename}</div>
      </div>

      <div className="sidebar-progress-bar">
        <div 
          className="sidebar-progress-fill"
          style={{ width: `${progress.progress_percentage}%` }}
        ></div>
      </div>
      
      <div className="sidebar-progress-percentage">
        {progress.progress_percentage}%
      </div>

      <div className="sidebar-current-stage">
        <div className="current-stage-icon">
          {progress.current_stage === 'completed' ? '✅' : 
           progress.current_stage === 'failed' ? '❌' : 
           stages.find(s => s.key === progress.current_stage)?.icon || '⏳'}
        </div>
        <div className="current-stage-text">
          {progress.current_stage === 'completed' ? 'Completed!' :
           progress.current_stage === 'failed' ? 'Failed' :
           getCurrentStageMessage()}
        </div>
      </div>

      <div className="sidebar-stage-dots">
        {stages.map((stage, index) => {
          const status = getStageStatus(stage.key);
          return (
            <div
              key={stage.key}
              className={`stage-dot ${status}`}
              title={`${stage.label}: ${status}`}
            >
              {status === 'completed' ? '●' : 
               status === 'active' ? '◐' : 
               status === 'failed' ? '●' : '○'}
            </div>
          );
        })}
      </div>

      {progress.current_stage === 'completed' && progress.processing_stats && (
        <div className="sidebar-success-stats">
          <div className="success-stat">
            📊 {progress.processing_stats.chunks_count} chunks
          </div>
          <div className="success-stat">
            🔗 {progress.processing_stats.embeddings_count} embeddings
          </div>
        </div>
      )}

      {progress.current_stage === 'failed' && progress.error_message && (
        <div className="sidebar-error">
          ⚠️ {progress.error_message}
        </div>
      )}
    </div>
  );
};

export default SidebarProgressIndicator;
