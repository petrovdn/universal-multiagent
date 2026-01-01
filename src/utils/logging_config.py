"""
Logging configuration for the multi-agent system.
Provides structured logging with JSON output and rotation.
"""

import logging
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict
from logging.handlers import RotatingFileHandler


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
        
        return json.dumps(log_data)


def setup_logging(
    log_level: str = "INFO",
    log_dir: Path = Path("logs"),
    enable_file_logging: bool = True
) -> None:
    """
    Setup logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        enable_file_logging: Whether to enable file logging
    """
    # Create log directory
    if enable_file_logging:
        log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler with JSON format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_formatter = JSONFormatter()
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handlers for different log types
    if enable_file_logging:
        # General application log
        app_handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=30
        )
        app_handler.setLevel(logging.INFO)
        app_handler.setFormatter(console_formatter)
        root_logger.addHandler(app_handler)
        
        # Error log
        error_handler = RotatingFileHandler(
            log_dir / "errors.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=30
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(console_formatter)
        root_logger.addHandler(error_handler)
        
        # Audit log (for MCP operations)
        audit_handler = RotatingFileHandler(
            log_dir / "audit.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=30
        )
        audit_handler.setLevel(logging.INFO)
        audit_handler.setFormatter(console_formatter)
        
        # Create separate audit logger
        audit_logger = logging.getLogger("audit")
        audit_logger.addHandler(audit_handler)
        audit_logger.setLevel(logging.INFO)
        audit_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)




