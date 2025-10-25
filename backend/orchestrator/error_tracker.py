"""
Error Tracking & Monitoring Module
Integrates with Google Cloud Logging for production error visibility
"""

import time
import traceback
import os
from typing import Optional, Dict, Any
from google.cloud import logging as cloud_logging
from enum import Enum

class ErrorType(Enum):
    """Standard error types for categorization"""
    CHAT_AGENT_FAILURE = "CHAT_AGENT_FAILURE"
    TRANSACTION_GENERATION_FAILURE = "TRANSACTION_GENERATION_FAILURE"
    CONTRACT_ANALYSIS_FAILURE = "CONTRACT_ANALYSIS_FAILURE"
    TOOL_EXECUTION_FAILURE = "TOOL_EXECUTION_FAILURE"
    FIRESTORE_ERROR = "FIRESTORE_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    API_ERROR = "API_ERROR"
    EXTERNAL_API_FAILURE = "EXTERNAL_API_FAILURE"
    MEMORY_LIMIT_ERROR = "MEMORY_LIMIT_ERROR"

class ErrorTracker:
    """Singleton error tracker for structured logging"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ErrorTracker, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize Cloud Logging client"""
        try:
            project_id = os.getenv("GCP_PROJECT", "avapilot")
            self.logging_client = cloud_logging.Client(project=project_id)
            self.logger = self.logging_client.logger('avapilot-errors')
            self.metrics_logger = self.logging_client.logger('avapilot-metrics')
            self.enabled = True
            print("[ERROR_TRACKER] ✅ Cloud Logging initialized")
        except Exception as e:
            print(f"[ERROR_TRACKER] ⚠️ Cloud Logging unavailable: {e}")
            print("[ERROR_TRACKER] Falling back to console logging")
            self.enabled = False
            self.logger = None
            self.metrics_logger = None
    
    def log_error(
        self,
        error_type: ErrorType,
        error_msg: str,
        context: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ):
        """
        Log an error with full context and stack trace
        
        Args:
            error_type: Category of error (from ErrorType enum)
            error_msg: Human-readable error message
            context: Additional context (conversation_id, user_address, etc.)
            exception: Original exception object if available
        """
        error_data = {
            "severity": "ERROR",
            "type": error_type.value,
            "message": error_msg,
            "context": context or {},
            "timestamp": time.time(),
            "stack_trace": traceback.format_exc() if exception else None
        }
        
        # Print to console (always)
        print(f"\n{'='*60}")
        print(f"[ERROR] {error_type.value}")
        print(f"{'='*60}")
        print(f"Message: {error_msg}")
        if context:
            print(f"Context: {context}")
        if exception:
            traceback.print_exc()
        print(f"{'='*60}\n")
        
        # Send to Cloud Logging
        if self.enabled and self.logger:
            try:
                self.logger.log_struct(error_data)
            except Exception as e:
                print(f"[ERROR_TRACKER] Failed to log to Cloud: {e}")
    
    def log_warning(
        self,
        warning_type: str,
        warning_msg: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Log a warning (non-critical issue)"""
        warning_data = {
            "severity": "WARNING",
            "type": warning_type,
            "message": warning_msg,
            "context": context or {},
            "timestamp": time.time()
        }
        
        print(f"[WARNING] {warning_type}: {warning_msg}")
        
        if self.enabled and self.logger:
            try:
                self.logger.log_struct(warning_data)
            except Exception as e:
                print(f"[ERROR_TRACKER] Failed to log warning: {e}")
    
    def log_metric(
        self,
        metric_name: str,
        value: Any,
        context: Optional[Dict[str, Any]] = None
    ):
        """Log a metric for monitoring"""
        metric_data = {
            "severity": "INFO",
            "metric": metric_name,
            "value": value,
            "context": context or {},
            "timestamp": time.time()
        }
        
        if self.enabled and self.metrics_logger:
            try:
                self.metrics_logger.log_struct(metric_data)
            except Exception as e:
                print(f"[ERROR_TRACKER] Failed to log metric: {e}")

# Global instance
error_tracker = ErrorTracker()

# Convenience functions
def log_error(
    error_type: ErrorType,
    error_msg: str,
    context: Optional[Dict[str, Any]] = None,
    exception: Optional[Exception] = None
):
    """Log an error"""
    error_tracker.log_error(error_type, error_msg, context, exception)

def log_warning(warning_type: str, warning_msg: str, context: Optional[Dict[str, Any]] = None):
    """Log a warning"""
    error_tracker.log_warning(warning_type, warning_msg, context)

def log_metric(metric_name: str, value: Any, context: Optional[Dict[str, Any]] = None):
    """Log a metric"""
    error_tracker.log_metric(metric_name, value, context)