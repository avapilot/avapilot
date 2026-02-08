"""
Error Tracking & Monitoring — Python logging (no cloud dependency)
"""

import logging
import time
import traceback
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger("avapilot")
metrics_logger = logging.getLogger("avapilot.metrics")


class ErrorType(Enum):
    CHAT_AGENT_FAILURE = "CHAT_AGENT_FAILURE"
    TRANSACTION_GENERATION_FAILURE = "TRANSACTION_GENERATION_FAILURE"
    CONTRACT_ANALYSIS_FAILURE = "CONTRACT_ANALYSIS_FAILURE"
    TOOL_EXECUTION_FAILURE = "TOOL_EXECUTION_FAILURE"
    STORAGE_ERROR = "STORAGE_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    API_ERROR = "API_ERROR"
    EXTERNAL_API_FAILURE = "EXTERNAL_API_FAILURE"
    MEMORY_LIMIT_ERROR = "MEMORY_LIMIT_ERROR"


class ErrorTracker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )
        logger.info("Error tracker initialized (local logging)")

    def log_error(
        self,
        error_type: ErrorType,
        error_msg: str,
        context: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ):
        logger.error(
            "%s | %s | ctx=%s",
            error_type.value,
            error_msg,
            context or {},
        )
        if exception:
            logger.error(traceback.format_exc())

    def log_warning(
        self,
        warning_type: str,
        warning_msg: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        logger.warning("%s | %s | ctx=%s", warning_type, warning_msg, context or {})

    def log_metric(
        self,
        metric_name: str,
        value: Any,
        context: Optional[Dict[str, Any]] = None,
    ):
        metrics_logger.info("%s=%s | ctx=%s", metric_name, value, context or {})


error_tracker = ErrorTracker()


def log_error(
    error_type: ErrorType,
    error_msg: str,
    context: Optional[Dict[str, Any]] = None,
    exception: Optional[Exception] = None,
):
    error_tracker.log_error(error_type, error_msg, context, exception)


def log_warning(warning_type: str, warning_msg: str, context: Optional[Dict[str, Any]] = None):
    error_tracker.log_warning(warning_type, warning_msg, context)


def log_metric(metric_name: str, value: Any, context: Optional[Dict[str, Any]] = None):
    error_tracker.log_metric(metric_name, value, context)
