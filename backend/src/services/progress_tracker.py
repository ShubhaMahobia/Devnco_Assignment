import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class ProgressStage(Enum):
    """Progress stages for document processing"""
    UPLOADING = "uploading"
    EXTRACTING = "extracting" 
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"

class ProgressTracker:
    """Tracks progress of document processing with real-time updates"""
    
    def __init__(self):
        # Store progress for each file being processed
        self.progress_data: Dict[str, Dict[str, Any]] = {}
        # Store event listeners for SSE
        self.listeners: Dict[str, List] = {}
    
    def start_processing(self, file_id: str, filename: str) -> None:
        """Initialize progress tracking for a file"""
        self.progress_data[file_id] = {
            "file_id": file_id,
            "filename": filename,
            "current_stage": ProgressStage.UPLOADING.value,
            "progress_percentage": 0,
            "stages": {
                ProgressStage.UPLOADING.value: {"status": "active", "message": "Uploading file...", "timestamp": None},
                ProgressStage.EXTRACTING.value: {"status": "pending", "message": "Extracting text...", "timestamp": None},
                ProgressStage.CHUNKING.value: {"status": "pending", "message": "Creating chunks...", "timestamp": None},
                ProgressStage.EMBEDDING.value: {"status": "pending", "message": "Generating embeddings...", "timestamp": None},
                ProgressStage.INDEXING.value: {"status": "pending", "message": "Indexing document...", "timestamp": None}
            },
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "error_message": None
        }
        self._notify_listeners(file_id)
    
    def update_stage(self, file_id: str, stage: ProgressStage, message: Optional[str] = None, progress: Optional[int] = None) -> None:
        """Update the current processing stage"""
        if file_id not in self.progress_data:
            return
        
        data = self.progress_data[file_id]
        
        # Update current stage
        data["current_stage"] = stage.value
        
        # Update progress percentage
        stage_progress = {
            ProgressStage.UPLOADING: 10,
            ProgressStage.EXTRACTING: 30,
            ProgressStage.CHUNKING: 50,
            ProgressStage.EMBEDDING: 75,
            ProgressStage.INDEXING: 90,
            ProgressStage.COMPLETED: 100,
            ProgressStage.FAILED: 0
        }
        data["progress_percentage"] = progress if progress is not None else stage_progress.get(stage, 0)
        
        # Mark previous stages as completed
        stage_order = [ProgressStage.UPLOADING, ProgressStage.EXTRACTING, ProgressStage.CHUNKING, ProgressStage.EMBEDDING, ProgressStage.INDEXING]
        current_index = stage_order.index(stage) if stage in stage_order else -1
        
        for i, s in enumerate(stage_order):
            if i < current_index:
                data["stages"][s.value]["status"] = "completed"
                if data["stages"][s.value]["timestamp"] is None:
                    data["stages"][s.value]["timestamp"] = datetime.now().isoformat()
            elif i == current_index:
                data["stages"][s.value]["status"] = "active"
                data["stages"][s.value]["timestamp"] = datetime.now().isoformat()
                if message:
                    data["stages"][s.value]["message"] = message
            else:
                data["stages"][s.value]["status"] = "pending"
        
        # Special handling for completed/failed states
        if stage == ProgressStage.COMPLETED:
            data["completed_at"] = datetime.now().isoformat()
            for s in stage_order:
                if data["stages"][s.value]["status"] != "completed":
                    data["stages"][s.value]["status"] = "completed"
                    data["stages"][s.value]["timestamp"] = datetime.now().isoformat()
        elif stage == ProgressStage.FAILED:
            data["error_message"] = message
            data["completed_at"] = datetime.now().isoformat()
            data["stages"][data["current_stage"]]["status"] = "failed"
        
        self._notify_listeners(file_id)
    
    def complete_processing(self, file_id: str, message: str = "Document processed successfully") -> None:
        """Mark processing as completed"""
        self.update_stage(file_id, ProgressStage.COMPLETED, message, 100)
    
    def fail_processing(self, file_id: str, error_message: str) -> None:
        """Mark processing as failed"""
        self.update_stage(file_id, ProgressStage.FAILED, error_message, 0)
    
    def get_progress(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get current progress for a file"""
        return self.progress_data.get(file_id)
    
    def cleanup_progress(self, file_id: str) -> None:
        """Clean up progress data after completion"""
        # Keep data for a while in case client needs to fetch it
        # In production, you might want to implement automatic cleanup after some time
        pass
    
    def add_listener(self, file_id: str, queue: asyncio.Queue) -> None:
        """Add SSE listener for progress updates"""
        if file_id not in self.listeners:
            self.listeners[file_id] = []
        self.listeners[file_id].append(queue)
    
    def remove_listener(self, file_id: str, queue: asyncio.Queue) -> None:
        """Remove SSE listener"""
        if file_id in self.listeners and queue in self.listeners[file_id]:
            self.listeners[file_id].remove(queue)
            if not self.listeners[file_id]:
                del self.listeners[file_id]
    
    def _notify_listeners(self, file_id: str) -> None:
        """Notify all listeners about progress update"""
        if file_id not in self.listeners:
            return
        
        progress_data = self.progress_data[file_id]
        
        # Remove disconnected listeners
        active_listeners = []
        for queue in self.listeners[file_id]:
            try:
                queue.put_nowait(progress_data)
                active_listeners.append(queue)
            except asyncio.QueueFull:
                # Skip full queues
                active_listeners.append(queue)
            except Exception:
                # Remove disconnected listeners
                pass
        
        self.listeners[file_id] = active_listeners
        if not active_listeners:
            del self.listeners[file_id]

# Global progress tracker instance
progress_tracker = ProgressTracker()
