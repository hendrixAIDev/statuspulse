"""
StatusPulse — Simple Uptime Monitoring Dashboard
Built by Hendrix ⚡ | https://hendrixaidev.github.io
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timezone, timedelta
import os
import base64
import json
import hashlib
import re
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

# Setup logging to file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('statuspulse_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load .env file explicitly
load_dotenv()
logger.info(f"STARTUP - .env loaded. DEV_MODE={os.getenv('DEV_MODE')}")
print(f"[STARTUP] .env loaded. DEV_MODE={os.getenv('DEV_MODE')}")

# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="StatusPulse — Uptime Monitoring",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* StatusPulse Brand Colors */
    :root {
        --sp-green: #059669;
        --sp-red: #DC2626;
        --sp-yellow: #D97706;
        --sp-blue: #2563EB;
        --sp-gray: #6B7280;
    }
    
    /* Clean header */
    .stApp header { background: transparent; }
    
    /* Monitor cards */
    .monitor-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        margin: 8px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border-left: 4px solid var(--sp-green);
    }
    .monitor-card.down {
        border-left-color: var(--sp-red);
    }
    .monitor-card.unknown {
        border-left-color: var(--sp-gray);
    }
    
    /* Status badges */
    .status-up { color: var(--sp-green); font-weight: 700; }
    .status-down { color: var(--sp-red); font-weight: 700; }
    .status-unknown { color: var(--sp-gray); font-weight: 700; }
    
    /* Uptime bar */
    .uptime-bar {
        display: flex;
        gap: 1px;
        height: 24px;
        border-radius: 4px;
        overflow: hidden;
    }
    .uptime-segment {
        flex: 1;
        min-width: 2px;
    }
    .uptime-segment.up { background: var(--sp-green); }
    .uptime-segment.down { background: var(--sp-red); }
    .uptime-segment.unknown { background: #E5E7EB; }
    
    /* Metrics */
    [data-testid="stMetric"] {
        background: white;
        padding: 16px;
        border-radius: 8px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    
    /* Hide streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    
    /* Sidebar styling */
    .css-1d391kg { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)


# ─── Dev Mode & Utilities ────────────────────────────────────────────────────
def is_dev_mode() -> bool:
    """Check if dev mode is enabled."""
    dev_mode = os.getenv("DEV_MODE", "false").lower() in ("true", "1", "yes")
    logger.debug(f"DEV_MODE - Environment variable: {os.getenv('DEV_MODE')}")
    logger.debug(f"DEV_MODE - Evaluated as: {dev_mode}")
    print(f"[DEV_MODE] Environment variable: {os.getenv('DEV_MODE')}")
    print(f"[DEV_MODE] Evaluated as: {dev_mode}")
    return dev_mode


def validate_email(email: str) -> bool:
    """
    Validate email format. Accepts standard formats including plus addressing.
    Examples: user@example.com, user+tag@domain.com, first.last@example.co.uk
    """
    if not email or "@" not in email:
        return False
    
    # RFC 5322 compliant regex (simplified but covers common cases)
    # Accepts: alphanumeric, dots, hyphens, plus signs, underscores
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


# Rate limiting state (in-memory for simplicity)
_signup_attempts = {}

def check_rate_limit(email: str) -> tuple[bool, str]:
    """
    Check if signup is rate limited. Returns (allowed, error_message).
    In dev mode, always allows.
    """
    if is_dev_mode():
        return True, ""
    
    now = datetime.now(timezone.utc)
    
    # Clean old entries (older than 1 hour)
    cutoff = now - timedelta(hours=1)
    _signup_attempts.clear()  # Simple approach: clear all on each check
    
    if email in _signup_attempts:
        last_attempt = _signup_attempts[email]
        elapsed = (now - last_attempt).total_seconds()
        
        # Allow 1 signup per 60 seconds per email
        if elapsed < 60:
            wait_time = int(60 - elapsed)
            return False, f"Rate limit exceeded. Please wait {wait_time} seconds before trying again."
    
    _signup_attempts[email] = now
    return True, ""


# ─── Supabase Connection ────────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    if not url or not key:
        st.error("⚠️ Supabase not configured. Set SUPABASE_URL and SUPABASE_KEY.")
        st.stop()
    return create_client(url, key)


@st.cache_resource
def get_supabase_admin() -> Client:
    """Get Supabase client with service key (admin access)."""
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or st.secrets.get("SUPABASE_SERVICE_KEY", "")
    if not url or not service_key:
        return None
    return create_client(url, service_key)


# ─── Session Management (using st.query_params) ─────────────────────────────
def get_session():
    """Restore session from query params."""
    params = st.query_params
    token = params.get("s", "")
    if token:
        try:
            data = json.loads(base64.b64decode(token).decode())
            return data
        except Exception:
            pass
    return None


def set_session(user_data: dict):
    """Save session to query params."""
    token = base64.b64encode(json.dumps(user_data).encode()).decode()
    st.query_params["s"] = token


def clear_session():
    """Clear the session."""
    st.query_params.clear()


# ─── Auth Functions ──────────────────────────────────────────────────────────
def signup(email: str, password: str, display_name: str = ""):
    """Sign up a new user."""
    logger.info(f"SIGNUP - Starting signup for {email}")
    print(f"[SIGNUP] Starting signup for {email}")
    
    # Validate email format
    if not validate_email(email):
        logger.warning(f"SIGNUP - Invalid email format: {email}")
        return {"success": False, "error": "Invalid email format. Please use a valid email address."}
    
    # Check rate limit (bypassed in dev mode)
    allowed, error = check_rate_limit(email)
    if not allowed:
        logger.warning(f"SIGNUP - Rate limited: {email}")
        return {"success": False, "error": error}
    
    try:
        # In dev mode, use admin API to bypass Supabase rate limiting
        if is_dev_mode():
            logger.info(f"SIGNUP - DEV_MODE detected - using admin API")
            print(f"[SIGNUP] DEV_MODE detected - using admin API")
            sb_admin = get_supabase_admin()
            if sb_admin:
                try:
                    logger.info(f"SIGNUP - Admin client created, calling create_user")
                    print(f"[SIGNUP] Admin client created, calling create_user")
                    result = sb_admin.auth.admin.create_user({
                        "email": email,
                        "password": password,
                        "email_confirm": True,  # Auto-confirm
                        "user_metadata": {
                            "display_name": display_name or email.split("@")[0]
                        }
                    })
                    
                    logger.info(f"SIGNUP - Admin API result: user exists={bool(result.user)}")
                    print(f"[SIGNUP] Admin API result: {result}")
                    
                    if result.user:
                        logger.info(f"SIGNUP - User created successfully via admin API: {result.user.id}")
                        logger.info(f"SIGNUP - User email_confirmed_at: {result.user.email_confirmed_at}")
                        print(f"[SIGNUP] User created successfully via admin API: {result.user.id}")
                        print(f"[SIGNUP] User email_confirmed_at: {getattr(result.user, 'email_confirmed_at', 'NOT SET')}")
                        return {
                            "success": True,
                            "user_id": result.user.id,
                            "email": email,
                            "dev_mode": True
                        }
                except Exception as e:
                    # If admin API fails, fall back to regular signup
                    error_msg = str(e)
                    logger.error(f"SIGNUP - Admin API error: {error_msg}")
                    print(f"[SIGNUP] Admin API error: {error_msg}")
                    if "already registered" in error_msg.lower() or "duplicate" in error_msg.lower():
                        return {"success": False, "error": "Email already registered. Try logging in instead."}
                    # Fall through to regular signup if other error
            else:
                logger.warning(f"SIGNUP - Admin client not available - falling back to regular signup")
                print(f"[SIGNUP] Admin client not available - falling back to regular signup")
        
        # Regular signup (production or dev mode fallback)
        sb = get_supabase()
        signup_options = {
            "email": email,
            "password": password,
            "options": {
                "data": {"display_name": display_name or email.split("@")[0]}
            }
        }
        
        result = sb.auth.sign_up(signup_options)
        
        if result.user:
            return {"success": True, "user_id": result.user.id, "email": email}
        return {"success": False, "error": "Signup failed"}
        
    except Exception as e:
        error_msg = str(e)
        # Make rate limit errors more user-friendly
        if "rate" in error_msg.lower() or "too many" in error_msg.lower():
            if is_dev_mode():
                return {"success": False, "error": "Rate limit hit even in dev mode. This is a Supabase limitation. Try the seed script instead: python seed_test_accounts.py"}
            return {"success": False, "error": "Too many signup attempts. Please wait a few minutes and try again."}
        if "already registered" in error_msg.lower() or "duplicate" in error_msg.lower():
            return {"success": False, "error": "Email already registered. Try logging in instead."}
        return {"success": False, "error": error_msg}


def login(email: str, password: str):
    """Log in an existing user."""
    logger.info(f"LOGIN - Attempting login for {email}")
    print(f"[LOGIN] Attempting login for {email}")
    sb = get_supabase()
    try:
        result = sb.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        logger.info(f"LOGIN - Auth result received: user_exists={bool(result.user)}")
        print(f"[LOGIN] Auth result: {result}")
        
        if result.user:
            logger.info(f"LOGIN - Login successful for user: {result.user.id}")
            logger.info(f"LOGIN - User email_confirmed_at: {result.user.email_confirmed_at}")
            print(f"[LOGIN] Login successful for user: {result.user.id}")
            print(f"[LOGIN] User email_confirmed_at: {getattr(result.user, 'email_confirmed_at', 'NOT SET')}")
            return {
                "success": True,
                "user_id": result.user.id,
                "email": email,
                "access_token": result.session.access_token
            }
        return {"success": False, "error": "Login failed"}
    except Exception as e:
        error_msg = str(e)
        logger.error(f"LOGIN - Login error: {error_msg}")
        print(f"[LOGIN] Login error: {error_msg}")
        return {"success": False, "error": error_msg}


# ─── Data Functions ──────────────────────────────────────────────────────────
def get_monitors(user_id: str):
    """Get all monitors for a user."""
    sb = get_supabase()
    result = sb.table("monitors").select("*").eq("user_id", user_id).order("created_at").execute()
    return result.data or []


def add_monitor(user_id: str, name: str, url: str, method: str = "GET",
                expected_status: int = 200):
    """Add a new monitor."""
    sb = get_supabase()
    
    # Check monitor limit
    profile = sb.table("profiles").select("max_monitors, plan").eq("id", user_id).single().execute()
    current_count = len(get_monitors(user_id))
    
    if current_count >= (profile.data or {}).get("max_monitors", 3):
        plan = (profile.data or {}).get("plan", "free")
        if plan == "free":
            return {"success": False, "error": "Free tier limit reached (3 monitors). Upgrade to Pro for unlimited."}
        return {"success": False, "error": "Monitor limit reached."}
    
    # Validate URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    result = sb.table("monitors").insert({
        "user_id": user_id,
        "name": name,
        "url": url,
        "method": method,
        "expected_status": expected_status
    }).execute()
    
    if result.data:
        # Auto-create email alert
        monitor_id = result.data[0]["id"]
        profile_data = sb.table("profiles").select("email").eq("id", user_id).single().execute()
        if profile_data.data:
            sb.table("alert_configs").insert({
                "monitor_id": monitor_id,
                "alert_type": "email",
                "destination": profile_data.data["email"],
                "is_active": True
            }).execute()
        
        return {"success": True, "monitor": result.data[0]}
    
    return {"success": False, "error": "Failed to create monitor"}


def update_monitor(monitor_id: str, name: str, url: str, method: str = "GET",
                   expected_status: int = 200, check_interval_seconds: int = 300,
                   timeout_seconds: int = 30):
    """Update an existing monitor's settings."""
    sb = get_supabase()
    
    # Validate URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    result = sb.table("monitors").update({
        "name": name,
        "url": url,
        "method": method,
        "expected_status": expected_status,
        "check_interval_seconds": check_interval_seconds,
        "timeout_seconds": timeout_seconds,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", monitor_id).execute()
    
    if result.data:
        return {"success": True, "monitor": result.data[0]}
    return {"success": False, "error": "Failed to update monitor"}


def delete_monitor(monitor_id: str):
    """Delete a monitor and its related data."""
    sb = get_supabase()
    sb.table("checks").delete().eq("monitor_id", monitor_id).execute()
    sb.table("incidents").delete().eq("monitor_id", monitor_id).execute()
    sb.table("alert_configs").delete().eq("monitor_id", monitor_id).execute()
    sb.table("alert_history").delete().eq("monitor_id", monitor_id).execute()
    sb.table("monitors").delete().eq("id", monitor_id).execute()


def get_recent_checks(monitor_id: str, hours: int = 24):
    """Get recent check results."""
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    result = sb.table("checks")\
        .select("*")\
        .eq("monitor_id", monitor_id)\
        .gte("checked_at", since)\
        .order("checked_at", desc=True)\
        .limit(500)\
        .execute()
    return result.data or []


def get_incidents(monitor_id: str, limit: int = 10):
    """Get recent incidents for a monitor."""
    sb = get_supabase()
    result = sb.table("incidents")\
        .select("*")\
        .eq("monitor_id", monitor_id)\
        .order("started_at", desc=True)\
        .limit(limit)\
        .execute()
    return result.data or []


def get_uptime_percentage(monitor_id: str, days: int = 30):
    """Calculate uptime percentage."""
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    checks = sb.table("checks")\
        .select("is_up")\
        .eq("monitor_id", monitor_id)\
        .gte("checked_at", since)\
        .execute()
    
    if not checks.data:
        return 100.0
    
    total = len(checks.data)
    up = sum(1 for c in checks.data if c["is_up"])
    return round((up / total) * 100, 2)


def trigger_check(monitor_id: str):
    """Manually trigger a check for a monitor."""
    from monitor_engine import MonitorEngine
    sb = get_supabase()
    
    monitor = sb.table("monitors").select("*").eq("id", monitor_id).single().execute()
    if not monitor.data:
        return None
    
    engine = MonitorEngine(sb)
    result = engine.run_check(
        url=monitor.data["url"],
        method=monitor.data["method"],
        expected_status=monitor.data["expected_status"],
        timeout=monitor.data["timeout_seconds"]
    )
    
    engine.save_check_result(monitor_id, result)
    engine.update_monitor_status(monitor_id, result["is_up"])
    
    return result


# ─── UI Components ──────────────────────────────────────────────────────────
def render_status_badge(status: str):
    """Render a colored status badge."""
    colors = {
        "up": ("🟢", "#059669", "UP"),
        "down": ("🔴", "#DC2626", "DOWN"),
        "unknown": ("⚪", "#6B7280", "UNKNOWN"),
        "paused": ("⏸️", "#D97706", "PAUSED")
    }
    emoji, color, label = colors.get(status, colors["unknown"])
    return f'{emoji} <span style="color:{color};font-weight:700">{label}</span>'


def render_uptime_bar(checks: list, hours: int = 24):
    """Render a visual uptime bar from check data."""
    if not checks:
        return '<div class="uptime-bar"><div class="uptime-segment unknown" style="width:100%"></div></div>'
    
    # Group checks into time buckets
    segments = 48  # One segment per 30 min for 24h
    bucket_size = timedelta(hours=hours) / segments
    now = datetime.now(timezone.utc)
    
    html = '<div class="uptime-bar">'
    for i in range(segments):
        bucket_start = now - timedelta(hours=hours) + (bucket_size * i)
        bucket_end = bucket_start + bucket_size
        
        bucket_checks = [c for c in checks 
                        if bucket_start <= datetime.fromisoformat(
                            c["checked_at"].replace("Z", "+00:00")
                        ) < bucket_end]
        
        if not bucket_checks:
            css_class = "unknown"
        elif all(c["is_up"] for c in bucket_checks):
            css_class = "up"
        else:
            css_class = "down"
        
        html += f'<div class="uptime-segment {css_class}"></div>'
    
    html += '</div>'
    return html


def render_response_time_chart(checks: list, monitor_name: str = ""):
    """Render a response time chart using Plotly."""
    if not checks:
        st.info("No check data available yet.")
        return
    
    df = pd.DataFrame(checks)
    df["checked_at"] = pd.to_datetime(df["checked_at"])
    df = df.sort_values("checked_at")
    
    # Filter out failed checks (no response time)
    df_valid = df[df["response_time_ms"].notna()]
    
    if df_valid.empty:
        st.warning("No successful checks to chart.")
        return
    
    fig = go.Figure()
    
    # Response time line
    fig.add_trace(go.Scatter(
        x=df_valid["checked_at"],
        y=df_valid["response_time_ms"],
        mode="lines+markers",
        name="Response Time",
        line=dict(color="#2563EB", width=2),
        marker=dict(size=4),
        hovertemplate="<b>%{x}</b><br>Response: %{y}ms<extra></extra>"
    ))
    
    # Mark downtime periods
    df_down = df[~df["is_up"]]
    if not df_down.empty:
        fig.add_trace(go.Scatter(
            x=df_down["checked_at"],
            y=[0] * len(df_down),
            mode="markers",
            name="Down",
            marker=dict(color="#DC2626", size=10, symbol="x"),
            hovertemplate="<b>%{x}</b><br>DOWN<extra></extra>"
        ))
    
    fig.update_layout(
        title=f"Response Time — {monitor_name}" if monitor_name else "Response Time",
        xaxis_title="Time",
        yaxis_title="Response Time (ms)",
        template="plotly_white",
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)


# ─── Pages ──────────────────────────────────────────────────────────────────
def page_auth():
    """Login/Signup page."""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="text-align:center; padding: 40px 0 20px;">
            <h1 style="font-size: 2.5rem;">📡 StatusPulse</h1>
            <p style="color: #6B7280; font-size: 1.1rem;">Simple uptime monitoring for developers</p>
        </div>
        """, unsafe_allow_html=True)
        
        tab_login, tab_signup = st.tabs(["🔑 Login", "✨ Sign Up"])
        
        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log In", use_container_width=True)
                
                if submitted and email and password:
                    result = login(email, password)
                    if result["success"]:
                        set_session({
                            "user_id": result["user_id"],
                            "email": result["email"],
                            "token": result["access_token"]
                        })
                        st.success("Welcome back! 🎉")
                        st.rerun()
                    else:
                        st.error(f"Login failed: {result['error']}")
        
        with tab_signup:
            # Show dev mode indicator
            if is_dev_mode():
                st.info("🔧 **Dev Mode Active** — Email confirmation disabled, no rate limits")
            
            with st.form("signup_form"):
                name = st.text_input("Display Name")
                email = st.text_input("Email", key="signup_email", 
                                     help="Accepts standard formats including plus addressing (user+tag@domain.com)")
                password = st.text_input("Password", type="password", key="signup_pass",
                                        help="Minimum 6 characters")
                password2 = st.text_input("Confirm Password", type="password")
                submitted = st.form_submit_button("Create Account", use_container_width=True)
                
                if submitted:
                    if not email or not password:
                        st.error("Email and password are required")
                    elif not validate_email(email):
                        st.error("Invalid email format. Examples: user@example.com, user+tag@domain.com")
                    elif password != password2:
                        st.error("Passwords don't match")
                    elif len(password) < 6:
                        st.error("Password must be at least 6 characters")
                    else:
                        result = signup(email, password, name)
                        if result["success"]:
                            if result.get("dev_mode"):
                                st.success("✅ Account created! You can log in immediately (dev mode).")
                            else:
                                st.success("✅ Account created! Check your email to confirm, then log in.")
                        else:
                            st.error(f"Signup failed: {result['error']}")
        
        st.markdown("""
        <div style="text-align:center; padding: 30px 0; color: #9CA3AF; font-size: 0.85rem;">
            <p>Free tier: 3 monitors • 5-min checks • Email alerts</p>
            <p>Built by <a href="https://hendrixaidev.github.io" target="_blank">Hendrix</a> ⚡</p>
        </div>
        """, unsafe_allow_html=True)


def page_dashboard(session: dict):
    """Main dashboard page."""
    user_id = session["user_id"]
    monitors = get_monitors(user_id)
    
    # Header
    st.markdown("""
    <div style="display:flex; justify-content:space-between; align-items:center; padding-bottom:20px;">
        <h1 style="margin:0;">📡 StatusPulse</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"**{session.get('email', 'User')}**")
        
        st.markdown("---")
        
        # Add monitor form
        st.subheader("➕ Add Monitor")
        with st.form("add_monitor"):
            name = st.text_input("Name", placeholder="My Website")
            url = st.text_input("URL", placeholder="https://example.com")
            method = st.selectbox("Method", ["GET", "HEAD", "POST"])
            expected = st.number_input("Expected Status", value=200, min_value=100, max_value=599)
            
            if st.form_submit_button("Add Monitor", use_container_width=True):
                if name and url:
                    result = add_monitor(user_id, name, url, method, expected)
                    if result["success"]:
                        st.success(f"✅ Added {name}")
                        st.rerun()
                    else:
                        st.error(result["error"])
                else:
                    st.warning("Name and URL are required")
        
        st.markdown("---")
        
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
        
        if st.button("🚪 Logout", use_container_width=True):
            clear_session()
            st.rerun()
    
    # Main content
    if not monitors:
        st.markdown("""
        <div style="text-align:center; padding: 60px 20px;">
            <h2>👋 Welcome to StatusPulse!</h2>
            <p style="color: #6B7280; font-size: 1.1rem;">
                Add your first monitor using the sidebar to start tracking uptime.
            </p>
            <p style="color: #9CA3AF;">
                Free tier: 3 monitors • 5-minute checks • Email alerts
            </p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Summary metrics
    up_count = sum(1 for m in monitors if m["current_status"] == "up")
    down_count = sum(1 for m in monitors if m["current_status"] == "down")
    unknown_count = sum(1 for m in monitors if m["current_status"] in ("unknown", "paused"))
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Monitors", len(monitors))
    with col2:
        st.metric("🟢 Up", up_count)
    with col3:
        st.metric("🔴 Down", down_count)
    with col4:
        avg_uptime = 100.0
        if monitors:
            uptimes = []
            for m in monitors:
                if m["current_status"] != "unknown":
                    uptimes.append(get_uptime_percentage(m["id"], days=7))
            if uptimes:
                avg_uptime = round(sum(uptimes) / len(uptimes), 2)
        st.metric("7-Day Uptime", f"{avg_uptime}%")
    
    st.markdown("---")
    
    # Monitor list
    for monitor in monitors:
        status = monitor["current_status"]
        status_html = render_status_badge(status)
        checks = get_recent_checks(monitor["id"], hours=24)
        
        with st.expander(
            f"{'🟢' if status == 'up' else '🔴' if status == 'down' else '⚪'} "
            f"**{monitor['name']}** — {monitor['url']}",
            expanded=(status == "down")
        ):
            # Status row
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                st.markdown(f"Status: {status_html}", unsafe_allow_html=True)
            with col2:
                uptime = get_uptime_percentage(monitor["id"], days=30)
                color = "#059669" if uptime >= 99.5 else "#D97706" if uptime >= 95 else "#DC2626"
                st.markdown(f"30d Uptime: <b style='color:{color}'>{uptime}%</b>", unsafe_allow_html=True)
            with col3:
                if checks:
                    latest = checks[0]
                    rt = latest.get("response_time_ms", "N/A")
                    st.markdown(f"Response: **{rt}ms**")
                else:
                    st.markdown("Response: **N/A**")
            with col4:
                last_check = monitor.get("last_checked_at", "Never")
                if last_check and last_check != "Never":
                    try:
                        dt = datetime.fromisoformat(last_check.replace("Z", "+00:00"))
                        elapsed = (datetime.now(timezone.utc) - dt).total_seconds()
                        if elapsed < 60:
                            last_check = f"{int(elapsed)}s ago"
                        elif elapsed < 3600:
                            last_check = f"{int(elapsed/60)}m ago"
                        else:
                            last_check = f"{int(elapsed/3600)}h ago"
                    except (ValueError, TypeError):
                        pass
                st.markdown(f"Last check: **{last_check}**")
            
            # Uptime bar
            if checks:
                uptime_html = render_uptime_bar(checks, hours=24)
                st.markdown(uptime_html, unsafe_allow_html=True)
                st.caption("Last 24 hours — green = up, red = down, gray = no data")
            
            # Response time chart
            render_response_time_chart(checks, monitor["name"])
            
            # Incidents
            incidents = get_incidents(monitor["id"], limit=5)
            if incidents:
                st.markdown("**Recent Incidents:**")
                for inc in incidents:
                    resolved = "✅ Resolved" if inc["is_resolved"] else "🔴 Ongoing"
                    duration = ""
                    if inc.get("duration_seconds"):
                        mins = inc["duration_seconds"] // 60
                        secs = inc["duration_seconds"] % 60
                        duration = f" ({mins}m {secs}s)"
                    st.markdown(f"- {resolved} — Started {inc['started_at'][:19]}{duration}")
            
            # Actions
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("🔍 Check Now", key=f"check_{monitor['id']}"):
                    with st.spinner("Checking..."):
                        result = trigger_check(monitor["id"])
                        if result:
                            if result["is_up"]:
                                st.success(f"✅ UP — {result['response_time_ms']}ms")
                            else:
                                st.error(f"🔴 DOWN — {result.get('error_message', 'Unknown error')}")
                        st.rerun()
            with col2:
                # Edit monitor
                edit_key = f"edit_mode_{monitor['id']}"
                if edit_key not in st.session_state:
                    st.session_state[edit_key] = False
                if st.button("✏️ Edit", key=f"edit_{monitor['id']}"):
                    st.session_state[edit_key] = not st.session_state[edit_key]
                    st.rerun()
            with col3:
                # Toggle active/paused
                is_active = monitor["is_active"]
                label = "⏸️ Pause" if is_active else "▶️ Resume"
                if st.button(label, key=f"toggle_{monitor['id']}"):
                    sb = get_supabase()
                    new_status = "paused" if is_active else "unknown"
                    sb.table("monitors").update({
                        "is_active": not is_active,
                        "current_status": new_status
                    }).eq("id", monitor["id"]).execute()
                    st.rerun()
            with col4:
                # Two-click delete confirmation
                delete_confirm_key = f"delete_confirm_{monitor['id']}"
                if delete_confirm_key not in st.session_state:
                    st.session_state[delete_confirm_key] = False
                
                if not st.session_state[delete_confirm_key]:
                    if st.button("🗑️ Delete", key=f"delete_{monitor['id']}"):
                        st.session_state[delete_confirm_key] = True
                        st.rerun()
                else:
                    st.warning("⚠️ Are you sure?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✅ Yes", key=f"delete_yes_{monitor['id']}", use_container_width=True):
                            delete_monitor(monitor["id"])
                            st.session_state[delete_confirm_key] = False
                            st.success(f"Deleted {monitor['name']}")
                            st.rerun()
                    with col_no:
                        if st.button("❌ No", key=f"delete_no_{monitor['id']}", use_container_width=True):
                            st.session_state[delete_confirm_key] = False
                            st.rerun()
            
            # Edit form (shown when edit mode is active)
            edit_key = f"edit_mode_{monitor['id']}"
            if st.session_state.get(edit_key, False):
                st.markdown("---")
                st.markdown("**✏️ Edit Monitor Settings**")
                with st.form(f"edit_form_{monitor['id']}"):
                    edit_col1, edit_col2 = st.columns(2)
                    with edit_col1:
                        edit_name = st.text_input("Name", value=monitor["name"], key=f"edit_name_{monitor['id']}")
                        edit_url = st.text_input("URL", value=monitor["url"], key=f"edit_url_{monitor['id']}")
                        edit_method = st.selectbox(
                            "Method", ["GET", "HEAD", "POST"],
                            index=["GET", "HEAD", "POST"].index(monitor["method"]),
                            key=f"edit_method_{monitor['id']}"
                        )
                    with edit_col2:
                        edit_expected = st.number_input(
                            "Expected Status", value=monitor["expected_status"],
                            min_value=100, max_value=599,
                            key=f"edit_expected_{monitor['id']}"
                        )
                        interval_options = {
                            60: "1 minute",
                            120: "2 minutes",
                            300: "5 minutes",
                            600: "10 minutes",
                            900: "15 minutes",
                            1800: "30 minutes",
                            3600: "1 hour"
                        }
                        current_interval = monitor.get("check_interval_seconds", 300)
                        interval_keys = list(interval_options.keys())
                        current_idx = interval_keys.index(current_interval) if current_interval in interval_keys else 2
                        edit_interval = st.selectbox(
                            "Check Interval",
                            options=interval_keys,
                            format_func=lambda x: interval_options[x],
                            index=current_idx,
                            key=f"edit_interval_{monitor['id']}"
                        )
                        edit_timeout = st.number_input(
                            "Timeout (seconds)", value=monitor.get("timeout_seconds", 30),
                            min_value=5, max_value=120,
                            key=f"edit_timeout_{monitor['id']}"
                        )
                    
                    submit_col1, submit_col2 = st.columns(2)
                    with submit_col1:
                        if st.form_submit_button("💾 Save Changes", use_container_width=True):
                            if edit_name and edit_url:
                                result = update_monitor(
                                    monitor["id"], edit_name, edit_url, edit_method,
                                    edit_expected, edit_interval, edit_timeout
                                )
                                if result["success"]:
                                    st.session_state[edit_key] = False
                                    st.success("✅ Monitor updated!")
                                    st.rerun()
                                else:
                                    st.error(result["error"])
                            else:
                                st.warning("Name and URL are required")


# ─── Public Status Page ─────────────────────────────────────────────────────
def page_status(slug: str):
    """Public status page view."""
    sb = get_supabase()
    
    # Find status page by slug
    page = sb.table("status_pages")\
        .select("*")\
        .eq("slug", slug)\
        .eq("is_public", True)\
        .single()\
        .execute()
    
    if not page.data:
        st.error("Status page not found.")
        return
    
    st.title(page.data.get("title", "Status Page"))
    if page.data.get("description"):
        st.markdown(page.data["description"])
    
    # Get monitors for this status page
    page_monitors = sb.table("status_page_monitors")\
        .select("monitor_id")\
        .eq("status_page_id", page.data["id"])\
        .order("display_order")\
        .execute()
    
    if not page_monitors.data:
        st.info("No monitors configured for this status page.")
        return
    
    all_up = True
    for pm in page_monitors.data:
        monitor = sb.table("monitors")\
            .select("*")\
            .eq("id", pm["monitor_id"])\
            .single()\
            .execute()
        
        if monitor.data:
            m = monitor.data
            status = m["current_status"]
            if status != "up":
                all_up = False
            
            checks = get_recent_checks(m["id"], hours=24)
            uptime = get_uptime_percentage(m["id"], days=30)
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"{render_status_badge(status)} **{m['name']}**", unsafe_allow_html=True)
            with col2:
                st.markdown(f"**{uptime}%** uptime (30d)")
            
            if checks:
                st.markdown(render_uptime_bar(checks, hours=24), unsafe_allow_html=True)
            st.markdown("---")
    
    # Overall status
    if all_up:
        st.success("🟢 All systems operational")
    else:
        st.warning("⚠️ Some systems are experiencing issues")
    
    st.caption("Powered by [StatusPulse](https://hendrixaidev.github.io) ⚡")


# ─── Main Router ────────────────────────────────────────────────────────────
def main():
    # Check for public status page route
    params = st.query_params
    if "status" in params:
        page_status(params["status"])
        return
    
    # Check session
    session = get_session()
    
    if session and session.get("user_id"):
        page_dashboard(session)
    else:
        page_auth()


if __name__ == "__main__":
    main()
