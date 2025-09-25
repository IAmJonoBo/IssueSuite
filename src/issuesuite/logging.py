"""Structured JSON logging for IssueSuite.

Provides configurable structured logging with JSON output format,
log levels, and performance timing capabilities.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Reserved LogRecord fields to avoid conflicts
        reserved_fields = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
            'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
            'thread', 'threadName', 'processName', 'process', 'message', 'exc_info',
            'exc_text', 'stack_info', 'taskName', 'getMessage', 'manager', 'disabled',
            'propagate', 'handlers', 'filters', 'addFilter', 'removeFilter', 'filter',
            'handle', 'addHandler', 'removeHandler', 'findCaller', 'makeRecord', 'debug',
            'info', 'warning', 'warn', 'error', 'exception', 'critical', 'log', 'isEnabledFor',
            'getEffectiveLevel', 'getChild', 'setLevel', 'hasHandlers'
        }
        
        # Add extra fields if present (and avoid reserved fields)
        if hasattr(record, 'operation'):
            log_entry['operation'] = record.operation
        if hasattr(record, 'external_id'):
            log_entry['external_id'] = record.external_id
        if hasattr(record, 'issue_number'):
            log_entry['issue_number'] = record.issue_number
        if hasattr(record, 'duration_ms'):
            log_entry['duration_ms'] = record.duration_ms
        if hasattr(record, 'dry_run'):
            log_entry['dry_run'] = record.dry_run
        if hasattr(record, 'error'):
            log_entry['error'] = record.error
            
        # Add any extra kwargs from the record, avoiding reserved fields
        for key, value in record.__dict__.items():
            if key not in reserved_fields and key not in log_entry and not key.startswith('_'):
                log_entry[key] = value
        
        return json.dumps(log_entry)


class StructuredLogger:
    """Structured logger for IssueSuite operations."""
    
    def __init__(self, name: str = 'issuesuite', json_logging: bool = False, level: str = 'INFO'):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Remove any existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Add console handler
        handler = logging.StreamHandler(sys.stdout)
        
        if json_logging:
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
        
        self.logger.addHandler(handler)
        self.logger.propagate = False
    
    def log_operation(self, operation: str, **kwargs: Any) -> None:
        """Log an operation with structured data."""
        extra = {'operation': operation, **kwargs}
        self.logger.info(f"Operation: {operation}", extra=extra)
    
    def log_issue_action(self, action: str, external_id: str, issue_number: Optional[int] = None, 
                        dry_run: bool = False, **kwargs: Any) -> None:
        """Log an issue-related action."""
        extra = {
            'operation': f'issue_{action}',
            'external_id': external_id,
            'dry_run': dry_run,
            **kwargs
        }
        if issue_number:
            extra['issue_number'] = issue_number
        
        message = f"Issue {action}: {external_id}"
        if issue_number:
            message += f" (#{issue_number})"
        if dry_run:
            message += " [DRY-RUN]"
            
        self.logger.info(message, extra=extra)
    
    def log_performance(self, operation: str, duration_ms: float, **kwargs: Any) -> None:
        """Log performance timing."""
        extra = {'operation': operation, 'duration_ms': round(duration_ms, 2), **kwargs}
        self.logger.info(f"Performance: {operation} completed in {duration_ms:.2f}ms", extra=extra)
    
    def log_error(self, message: str, error: Optional[str] = None, **kwargs: Any) -> None:
        """Log an error with structured data."""
        extra = kwargs
        if error:
            extra['error'] = str(error)
        self.logger.error(message, extra=extra)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self.logger.error(message, extra=kwargs)
    
    @contextmanager
    def timed_operation(self, operation: str, **kwargs: Any):
        """Context manager for timing operations."""
        start_time = time.perf_counter()
        try:
            self.log_operation(f"{operation}_start", **kwargs)
            yield
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_performance(operation, duration_ms, **kwargs)
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_error(f"Operation {operation} failed after {duration_ms:.2f}ms", 
                          error=str(e), **kwargs)
            raise


# Global logger instance
_global_logger: Optional[StructuredLogger] = None


def get_logger() -> StructuredLogger:
    """Get the global structured logger instance."""
    global _global_logger
    if _global_logger is None:
        _global_logger = StructuredLogger()
    return _global_logger


def configure_logging(json_logging: bool = False, level: str = 'INFO') -> StructuredLogger:
    """Configure global structured logging."""
    global _global_logger
    _global_logger = StructuredLogger(json_logging=json_logging, level=level)
    return _global_logger