"""
StatusPulse - SCHP (Status Capability Health Protocol) Client
Fetches and parses /health/capabilities endpoints per SCHP v1.0 spec.
"""

import httpx
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


class SCHPClient:
    """Client for fetching and parsing SCHP capability health endpoints."""
    
    SCHP_VERSION = "1.0"
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    async def fetch_capabilities(self, url: str) -> Dict[str, Any]:
        """
        Fetch capabilities from an SCHP endpoint.
        
        Args:
            url: The base URL or full /health/capabilities URL
            
        Returns:
            Dict with:
            - success: bool
            - data: SCHP response (if successful)
            - error: str (if failed)
            - response_time_ms: int
            - fetched_at: ISO timestamp
        """
        # Normalize URL
        if not url.endswith('/health/capabilities'):
            url = url.rstrip('/') + '/health/capabilities'
        
        result = {
            "success": False,
            "data": None,
            "error": None,
            "response_time_ms": None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "url": url
        }
        
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=self.timeout,
                verify=True
            ) as client:
                start = asyncio.get_event_loop().time()
                response = await client.get(url)
                end = asyncio.get_event_loop().time()
                
                result["response_time_ms"] = int((end - start) * 1000)
                
                if response.status_code != 200:
                    result["error"] = f"HTTP {response.status_code}"
                    return result
                
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    result["error"] = "Invalid JSON response"
                    return result
                
                # Validate SCHP structure
                validation = self._validate_schp_response(data)
                if not validation["valid"]:
                    result["error"] = f"Invalid SCHP: {validation['error']}"
                    return result
                
                result["success"] = True
                result["data"] = data
                
        except httpx.TimeoutException:
            result["error"] = f"Timeout after {self.timeout}s"
        except httpx.ConnectError as e:
            result["error"] = f"Connection failed: {str(e)[:200]}"
        except Exception as e:
            result["error"] = f"Error: {str(e)[:200]}"
            logger.exception(f"SCHP fetch error for {url}")
        
        return result
    
    def fetch_capabilities_sync(self, url: str) -> Dict[str, Any]:
        """Synchronous wrapper for fetch_capabilities."""
        return asyncio.run(self.fetch_capabilities(url))
    
    def _validate_schp_response(self, data: Dict) -> Dict[str, Any]:
        """Validate SCHP response structure."""
        if not isinstance(data, dict):
            return {"valid": False, "error": "Response must be object"}
        
        # Check required fields
        if "capabilities" not in data:
            return {"valid": False, "error": "Missing 'capabilities' field"}
        
        if not isinstance(data["capabilities"], dict):
            return {"valid": False, "error": "'capabilities' must be object"}
        
        # Validate each capability
        for name, cap in data["capabilities"].items():
            if not isinstance(cap, dict):
                return {"valid": False, "error": f"Capability '{name}' must be object"}
            
            if "ok" not in cap:
                return {"valid": False, "error": f"Capability '{name}' missing 'ok' field"}
            
            if not isinstance(cap["ok"], bool):
                return {"valid": False, "error": f"Capability '{name}' 'ok' must be boolean"}
        
        return {"valid": True, "error": None}
    
    def get_overall_status(self, data: Dict) -> str:
        """
        Determine overall status from capabilities.
        
        Returns: 'operational', 'degraded', or 'down'
        """
        if not data or "capabilities" not in data:
            return "unknown"
        
        # If explicit status provided, use it
        if "status" in data:
            return data["status"]
        
        # Otherwise, derive from capabilities
        caps = data["capabilities"]
        if not caps:
            return "unknown"
        
        all_ok = all(c.get("ok", False) for c in caps.values())
        any_ok = any(c.get("ok", False) for c in caps.values())
        
        if all_ok:
            return "operational"
        elif any_ok:
            return "degraded"
        else:
            return "down"
    
    def get_failed_capabilities(self, data: Dict) -> list:
        """Get list of capability names that are not ok."""
        if not data or "capabilities" not in data:
            return []
        
        return [
            name for name, cap in data["capabilities"].items()
            if not cap.get("ok", True)
        ]
    
    def format_status_summary(self, data: Dict) -> str:
        """Format a human-readable status summary."""
        if not data:
            return "Unable to fetch capabilities"
        
        status = self.get_overall_status(data)
        caps = data.get("capabilities", {})
        total = len(caps)
        ok_count = sum(1 for c in caps.values() if c.get("ok", False))
        
        if status == "operational":
            return f"✅ Operational ({ok_count}/{total} capabilities OK)"
        elif status == "degraded":
            failed = self.get_failed_capabilities(data)
            return f"⚠️ Degraded — {', '.join(failed)} unavailable ({ok_count}/{total} OK)"
        else:
            return f"🔴 Down — All capabilities unavailable"


# Simple test
if __name__ == "__main__":
    # Test with a mock SCHP response
    client = SCHPClient()
    
    mock_response = {
        "schp_version": "1.0",
        "app": "test",
        "status": "degraded",
        "capabilities": {
            "ai_extraction": {"ok": False, "reason": "quota_exhausted"},
            "database": {"ok": True},
            "auth": {"ok": True}
        }
    }
    
    print("Overall status:", client.get_overall_status(mock_response))
    print("Failed:", client.get_failed_capabilities(mock_response))
    print("Summary:", client.format_status_summary(mock_response))
