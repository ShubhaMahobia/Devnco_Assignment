import logging
import os
from logging.handlers import RotatingFileHandler
from from_root import from_root
from datetime import datetime
from enum import Enum

# Constants for log configuration
LOG_DIR = 'logs'
LOG_FILE = f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.log"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB

# Define processing stages
class ProcessingStage(Enum):
    UPLOADING = "UPLOADING"
    EXTRACTING = "EXTRACTING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    INDEXING = "INDEXING"
    FAILED = "FAILED"

# Construct log file path
log_dir_path = os.path.join(from_root(), LOG_DIR)
os.makedirs(log_dir_path, exist_ok=True)
log_file_path = os.path.join(log_dir_path, LOG_FILE)

def configure_logger():
    """
    Configures logging with a rotating file handler and a console handler.
    """
    # Create a custom logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Define formatter with stage information
    formatter = logging.Formatter("[ %(asctime)s ] %(name)s - %(levelname)s - %(message)s")

    # File handler with rotation
    file_handler = RotatingFileHandler(log_file_path, maxBytes=MAX_LOG_SIZE)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

class StageLogger:
    """
    A wrapper class for logging with stage information.
    """
    
    def __init__(self, logger_name: str = __name__):
        self.logger = logging.getLogger(logger_name)
    
    def _log_with_stage(self, level: int, stage: ProcessingStage, message: str, *args, **kwargs):
        """
        Internal method to log with stage information.
        """
        stage_message = f"[{stage.value}] {message}"
        self.logger.log(level, stage_message, *args, **kwargs)
    
    def info(self, stage: ProcessingStage, message: str, *args, **kwargs):
        """Log info message with stage information."""
        self._log_with_stage(logging.INFO, stage, message, *args, **kwargs)
    
    def debug(self, stage: ProcessingStage, message: str, *args, **kwargs):
        """Log debug message with stage information."""
        self._log_with_stage(logging.DEBUG, stage, message, *args, **kwargs)
    
    def warning(self, stage: ProcessingStage, message: str, *args, **kwargs):
        """Log warning message with stage information."""
        self._log_with_stage(logging.WARNING, stage, message, *args, **kwargs)
    
    def error(self, stage: ProcessingStage, message: str, *args, **kwargs):
        """Log error message with stage information."""
        self._log_with_stage(logging.ERROR, stage, message, *args, **kwargs)
    
    def critical(self, stage: ProcessingStage, message: str, *args, **kwargs):
        """Log critical message with stage information."""
        self._log_with_stage(logging.CRITICAL, stage, message, *args, **kwargs)

# Configure the logger
configure_logger()

# Create a default stage logger instance
stage_logger = StageLogger()