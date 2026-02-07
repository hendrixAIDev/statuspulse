"""
StatusPulse - Core Monitoring Engine
Runs checks against monitored URLs and stores results in Supabase.
Supports both URL checks and SCHP capability checks.
Can run standalone (cron/scheduler) or be imported by the Streamlit app.
"""

import httpx
import asyncio
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import os
import json

from schp_client import SCHPClient


class MonitorEngine:
    """Core monitoring engine that checks URLs and manages incidents."""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.smtp_email = os.getenv("SMTP_EMAIL", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
    
    async def check_url(self, url: str, method: str = "GET", 
                         expected_status: int = 200, 
                         timeout: int = 30) -> dict:
        """Check a single URL and return results."""
        result = {
            "url": url,
            "is_up": False,
            "status_code": None,
            "response_time_ms": None,
            "error_message": None,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=timeout,
                verify=True
            ) as client:
                start = asyncio.get_event_loop().time()
                
                if method == "HEAD":
                    response = await client.head(url)
                elif method == "POST":
                    response = await client.post(url)
                else:
                    response = await client.get(url)
                
                end = asyncio.get_event_loop().time()
                response_time_ms = int((end - start) * 1000)
                
                result["status_code"] = response.status_code
                result["response_time_ms"] = response_time_ms
                result["is_up"] = response.status_code == expected_status
                
                if not result["is_up"]:
                    result["error_message"] = f"Expected {expected_status}, got {response.status_code}"
                    
        except httpx.TimeoutException:
            result["error_message"] = f"Timeout after {timeout}s"
        except httpx.ConnectError as e:
            result["error_message"] = f"Connection failed: {str(e)[:200]}"
        except httpx.TooManyRedirects:
            result["error_message"] = "Too many redirects"
        except Exception as e:
            result["error_message"] = f"Error: {str(e)[:200]}"
        
        return result
    
    def run_check(self, url: str, method: str = "GET",
                   expected_status: int = 200, timeout: int = 30) -> dict:
        """Synchronous wrapper for check_url."""
        return asyncio.run(self.check_url(url, method, expected_status, timeout))
    
    # ─── SCHP Capability Checking ────────────────────────────────────────────────
    
    async def check_capabilities(self, url: str, timeout: int = 30) -> dict:
        """
        Check capabilities via SCHP endpoint.
        
        Returns dict with:
        - url: The capabilities URL
        - is_up: True if all capabilities are ok
        - status: 'operational', 'degraded', or 'down'
        - capabilities: Dict of capability statuses
        - failed_capabilities: List of failed capability names
        - response_time_ms: Response time
        - error_message: Error if fetch failed
        - checked_at: Timestamp
        """
        schp = SCHPClient(timeout=timeout)
        result = await schp.fetch_capabilities(url)
        
        check_result = {
            "url": result["url"],
            "is_up": False,
            "status": "unknown",
            "capabilities": {},
            "failed_capabilities": [],
            "response_time_ms": result["response_time_ms"],
            "error_message": result["error"],
            "checked_at": result["fetched_at"]
        }
        
        if result["success"] and result["data"]:
            data = result["data"]
            check_result["status"] = schp.get_overall_status(data)
            check_result["capabilities"] = data.get("capabilities", {})
            check_result["failed_capabilities"] = schp.get_failed_capabilities(data)
            check_result["is_up"] = check_result["status"] == "operational"
        
        return check_result
    
    def run_capability_check(self, url: str, timeout: int = 30) -> dict:
        """Synchronous wrapper for check_capabilities."""
        return asyncio.run(self.check_capabilities(url, timeout))
    
    def save_capability_check_result(self, monitor_id: str, result: dict):
        """Save capability check result to Supabase."""
        self.supabase.table("checks").insert({
            "monitor_id": monitor_id,
            "status_code": 200 if result["is_up"] else 503,  # Synthetic status
            "response_time_ms": result["response_time_ms"],
            "is_up": result["is_up"],
            "error_message": result["error_message"] or (
                f"Degraded: {', '.join(result['failed_capabilities'])}" 
                if result["failed_capabilities"] else None
            ),
            "checked_at": result["checked_at"]
        }).execute()
    
    def save_check_result(self, monitor_id: str, result: dict):
        """Save check result to Supabase."""
        self.supabase.table("checks").insert({
            "monitor_id": monitor_id,
            "status_code": result["status_code"],
            "response_time_ms": result["response_time_ms"],
            "is_up": result["is_up"],
            "error_message": result["error_message"],
            "checked_at": result["checked_at"]
        }).execute()
    
    def update_monitor_status(self, monitor_id: str, is_up: bool):
        """Update monitor's current status and handle incidents."""
        # Get current monitor state
        monitor = self.supabase.table("monitors")\
            .select("*")\
            .eq("id", monitor_id)\
            .single()\
            .execute()
        
        if not monitor.data:
            return
        
        old_status = monitor.data["current_status"]
        new_status = "up" if is_up else "down"
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Update monitor status
        update_data = {
            "current_status": new_status,
            "last_checked_at": now,
            "updated_at": now
        }
        
        # Status changed?
        if old_status != new_status and old_status != "unknown":
            update_data["last_status_change_at"] = now
            
            if new_status == "down":
                # Create new incident
                self.supabase.table("incidents").insert({
                    "monitor_id": monitor_id,
                    "started_at": now,
                    "is_resolved": False
                }).execute()
                
                # Send alerts
                self._send_alerts(monitor_id, monitor.data, "down")
                
            elif new_status == "up" and old_status == "down":
                # Resolve open incidents
                open_incidents = self.supabase.table("incidents")\
                    .select("*")\
                    .eq("monitor_id", monitor_id)\
                    .eq("is_resolved", False)\
                    .execute()
                
                for incident in (open_incidents.data or []):
                    started = datetime.fromisoformat(incident["started_at"].replace("Z", "+00:00"))
                    duration = int((datetime.now(timezone.utc) - started).total_seconds())
                    
                    self.supabase.table("incidents").update({
                        "resolved_at": now,
                        "duration_seconds": duration,
                        "is_resolved": True
                    }).eq("id", incident["id"]).execute()
                
                # Send recovery alert
                self._send_alerts(monitor_id, monitor.data, "up")
        
        self.supabase.table("monitors")\
            .update(update_data)\
            .eq("id", monitor_id)\
            .execute()
    
    def _send_alerts(self, monitor_id: str, monitor_data: dict, status: str):
        """Send alerts for a monitor status change."""
        # Get alert configs for this monitor
        alerts = self.supabase.table("alert_configs")\
            .select("*")\
            .eq("monitor_id", monitor_id)\
            .eq("is_active", True)\
            .execute()
        
        for alert in (alerts.data or []):
            try:
                if alert["alert_type"] == "email":
                    self._send_email_alert(alert, monitor_data, status)
                elif alert["alert_type"] == "webhook":
                    self._send_webhook_alert(alert, monitor_data, status)
                
                # Log successful alert
                self.supabase.table("alert_history").insert({
                    "alert_config_id": alert["id"],
                    "monitor_id": monitor_id,
                    "alert_type": alert["alert_type"],
                    "message": f"{monitor_data['name']} is {status.upper()}",
                    "was_successful": True
                }).execute()
                
            except Exception as e:
                # Log failed alert
                self.supabase.table("alert_history").insert({
                    "alert_config_id": alert["id"],
                    "monitor_id": monitor_id,
                    "alert_type": alert["alert_type"],
                    "message": f"Failed: {str(e)[:200]}",
                    "was_successful": False
                }).execute()
    
    def _send_email_alert(self, alert_config: dict, monitor_data: dict, status: str):
        """Send email alert via SMTP."""
        if not self.smtp_email or not self.smtp_password:
            return
        
        name = monitor_data["name"]
        url = monitor_data["url"]
        
        if status == "down":
            subject = f"🔴 {name} is DOWN"
            body = f"""
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto;">
        <h2 style="color: #DC2626;">🔴 Monitor Down: {name}</h2>
        <p><strong>URL:</strong> <a href="{url}">{url}</a></p>
        <p><strong>Status:</strong> DOWN</p>
        <p><strong>Time:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <hr style="border: 1px solid #E5E7EB;">
        <p style="color: #6B7280; font-size: 12px;">StatusPulse — Simple Uptime Monitoring</p>
    </div>
</body>
</html>"""
        else:
            subject = f"🟢 {name} is back UP"
            body = f"""
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto;">
        <h2 style="color: #059669;">🟢 Monitor Recovered: {name}</h2>
        <p><strong>URL:</strong> <a href="{url}">{url}</a></p>
        <p><strong>Status:</strong> UP (recovered)</p>
        <p><strong>Time:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <hr style="border: 1px solid #E5E7EB;">
        <p style="color: #6B7280; font-size: 12px;">StatusPulse — Simple Uptime Monitoring</p>
    </div>
</body>
</html>"""
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"StatusPulse <{self.smtp_email}>"
        msg["To"] = alert_config["destination"]
        msg.attach(MIMEText(body, "html"))
        
        context = ssl.create_default_context()
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls(context=context)
            server.login(self.smtp_email, self.smtp_password)
            server.send_message(msg)
    
    def _send_webhook_alert(self, alert_config: dict, monitor_data: dict, status: str):
        """Send webhook alert via HTTP POST."""
        import httpx as httpx_sync
        
        payload = {
            "event": "monitor_status_changed",
            "monitor": {
                "name": monitor_data["name"],
                "url": monitor_data["url"],
                "status": status
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        httpx_sync.post(
            alert_config["destination"],
            json=payload,
            timeout=10
        )
    
    def run_all_checks(self):
        """Run checks for all active monitors that are due."""
        # Get all active monitors
        monitors = self.supabase.table("monitors")\
            .select("*")\
            .eq("is_active", True)\
            .execute()
        
        results = []
        for monitor in (monitors.data or []):
            # Check if it's time to check this monitor
            if monitor["last_checked_at"]:
                last_check = datetime.fromisoformat(
                    monitor["last_checked_at"].replace("Z", "+00:00")
                )
                elapsed = (datetime.now(timezone.utc) - last_check).total_seconds()
                if elapsed < monitor["check_interval_seconds"]:
                    continue
            
            # Run the check
            result = self.run_check(
                url=monitor["url"],
                method=monitor["method"],
                expected_status=monitor["expected_status"],
                timeout=monitor["timeout_seconds"]
            )
            
            # Save results
            self.save_check_result(monitor["id"], result)
            self.update_monitor_status(monitor["id"], result["is_up"])
            
            results.append({
                "monitor_name": monitor["name"],
                "url": monitor["url"],
                **result
            })
        
        return results


def run_monitoring_cycle(supabase_url: str, supabase_key: str):
    """Run a single monitoring cycle. Called by cron/scheduler."""
    from supabase import create_client
    
    client = create_client(supabase_url, supabase_key)
    engine = MonitorEngine(client)
    results = engine.run_all_checks()
    
    print(f"[{datetime.now(timezone.utc).isoformat()}] Checked {len(results)} monitors")
    for r in results:
        status = "UP" if r["is_up"] else "DOWN"
        print(f"  {r['monitor_name']}: {status} ({r.get('response_time_ms', 'N/A')}ms)")
    
    return results


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for monitoring engine
    
    if not url or not key:
        print("Error: Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables")
        exit(1)
    
    results = run_monitoring_cycle(url, key)
