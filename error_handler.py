"""
Standardized Error Handler for Hendrix Apps

Usage:
    from error_handler import ErrorHandler
    
    handler = ErrorHandler("MyApp")
    
    try:
        # risky operation
    except Exception as e:
        result = handler.handle(e, category="DB", context={"action": "save"})
        st.error(f"{result['message']} (Code: {result['error_code']})")
"""

import time
import logging
import traceback
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ErrorDetails:
    """Full error details for logging/storage."""
    error_code: str
    app: str
    category: str
    error_type: str
    error_message: str
    traceback_str: str
    context: dict
    timestamp: int
    timestamp_human: str


class ErrorHandler:
    """
    Standardized error handling for Hendrix apps.
    
    Categories:
        AUTH - Authentication (login, signup, session)
        DB   - Database (connection, query, save)
        API  - External API failures
        VAL  - Validation (invalid input)
        PERM - Permission (access denied, rate limits)
        SYS  - System (unexpected errors)
    """
    
    # User-friendly messages by category
    USER_MESSAGES = {
        "AUTH": "Unable to complete authentication. Please try again.",
        "DB": "Unable to save your data. Please check your connection and try again.",
        "API": "A service we depend on is temporarily unavailable. Please try again later.",
        "VAL": "Please check your input and try again.",
        "PERM": "You don't have permission to perform this action.",
        "SYS": "Something unexpected happened. Please try again."
    }
    
    def __init__(self, app_name: str, supabase_client=None):
        """
        Initialize error handler.
        
        Args:
            app_name: Name of the app (e.g., "StatusPulse")
            supabase_client: Optional Supabase client for persistent storage
        """
        self.app_name = app_name
        self.supabase = supabase_client
        self._error_log = {}  # In-memory fallback
    
    def handle(
        self, 
        error: Exception, 
        category: str = "SYS", 
        context: Optional[dict] = None,
        custom_message: Optional[str] = None
    ) -> dict:
        """
        Handle an error and return user-friendly response.
        
        Args:
            error: The exception that was caught
            category: Error category (AUTH, DB, API, VAL, PERM, SYS)
            context: Additional context for debugging
            custom_message: Override the default user message
        
        Returns:
            dict: {
                "error_code": "ERR-AUTH-1738851234",
                "message": "User-friendly message",
                "user_action": "How to report the error"
            }
        """
        # Generate unique error code
        timestamp = int(time.time())
        error_code = f"ERR-{category}-{timestamp}"
        
        # Build full error details
        details = ErrorDetails(
            error_code=error_code,
            app=self.app_name,
            category=category,
            error_type=type(error).__name__,
            error_message=str(error),
            traceback_str=traceback.format_exc(),
            context=context or {},
            timestamp=timestamp,
            timestamp_human=datetime.fromtimestamp(timestamp).isoformat()
        )
        
        # Log internally
        logger.error(f"[{error_code}] {details.error_type}: {details.error_message}")
        logger.debug(f"[{error_code}] Full traceback:\n{details.traceback_str}")
        logger.debug(f"[{error_code}] Context: {details.context}")
        
        # Also print for Streamlit Cloud logs
        print(f"[ERROR {error_code}] {details.error_type}: {details.error_message}")
        print(f"[ERROR {error_code}] Context: {details.context}")
        
        # Store for lookup
        self._store_error(details)
        
        # User-friendly response
        user_message = custom_message or self.USER_MESSAGES.get(category, self.USER_MESSAGES["SYS"])
        
        return {
            "error_code": error_code,
            "message": user_message,
            "user_action": f"If this persists, contact support with code {error_code}"
        }
    
    def _store_error(self, details: ErrorDetails):
        """Store error for later lookup."""
        # In-memory storage
        self._error_log[details.error_code] = asdict(details)
        
        # Keep only last 1000 errors in memory
        if len(self._error_log) > 1000:
            oldest_keys = sorted(self._error_log.keys())[:100]
            for key in oldest_keys:
                del self._error_log[key]
        
        # Persist to database if available
        if self.supabase:
            try:
                self.supabase.table("error_logs").insert({
                    "error_code": details.error_code,
                    "app": details.app,
                    "category": details.category,
                    "error_type": details.error_type,
                    "error_message": details.error_message,
                    "traceback": details.traceback_str,
                    "context": details.context,
                    "created_at": details.timestamp_human
                }).execute()
            except Exception as e:
                logger.warning(f"Failed to persist error to database: {e}")
    
    def lookup(self, error_code: str) -> dict:
        """
        Look up error details by code.
        
        Args:
            error_code: The error code to look up
        
        Returns:
            dict: Full error details or {"error": "Not found"}
        """
        # Check in-memory first
        if error_code in self._error_log:
            return self._error_log[error_code]
        
        # Check database if available
        if self.supabase:
            try:
                result = self.supabase.table("error_logs").select("*").eq("error_code", error_code).execute()
                if result.data:
                    return result.data[0]
            except Exception as e:
                logger.warning(f"Failed to lookup error in database: {e}")
        
        return {"error": "Not found", "error_code": error_code}
    
    def format_for_ui(self, error_response: dict) -> str:
        """
        Format error response for Streamlit UI display.
        
        Args:
            error_response: Response from handle()
        
        Returns:
            str: Formatted error message for st.error()
        """
        return f"""
❌ {error_response['message']}

**Error Code:** `{error_response['error_code']}`

_If this issue persists, please report this code to support._
"""


# Convenience function for simple usage
_default_handler = None

def get_handler(app_name: str = "HendrixApp") -> ErrorHandler:
    """Get or create the default error handler."""
    global _default_handler
    if _default_handler is None or _default_handler.app_name != app_name:
        _default_handler = ErrorHandler(app_name)
    return _default_handler
