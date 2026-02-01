#!/usr/bin/env python3
"""
StatusPulse Monitor Runner
Run this via cron or as a background service to perform periodic checks.

Usage:
    # Run once (for cron)
    python run_monitor.py

    # Run continuously with built-in scheduler
    python run_monitor.py --daemon

Cron example (every 5 minutes):
    */5 * * * * cd /path/to/statuspulse && /path/to/venv/bin/python run_monitor.py
"""

import os
import sys
import time
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


def run_once():
    """Run a single monitoring cycle."""
    from monitor_engine import run_monitoring_cycle
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        print("Error: Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
        sys.exit(1)
    
    results = run_monitoring_cycle(url, key)
    return results


def run_daemon(interval: int = 60):
    """Run monitoring continuously."""
    print(f"StatusPulse Monitor Daemon starting (interval: {interval}s)")
    print(f"Press Ctrl+C to stop")
    
    while True:
        try:
            results = run_once()
            if not results:
                print(f"[{datetime.now(timezone.utc).isoformat()}] No monitors due for checking")
        except Exception as e:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Error: {e}")
        
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StatusPulse Monitor Runner")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=60, 
                       help="Check interval in seconds (daemon mode)")
    args = parser.parse_args()
    
    if args.daemon:
        run_daemon(args.interval)
    else:
        run_once()
