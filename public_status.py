"""
StatusPulse — Standalone Public Status Page
A lightweight, embeddable status page that can run independently.
Deploy separately from the main dashboard for reliability.

Usage:
    streamlit run public_status.py -- --slug my-company
    
Or visit: http://your-app.streamlit.app?slug=my-company
"""

import streamlit as st
import os
import json
from datetime import datetime, timezone, timedelta
from supabase import create_client

st.set_page_config(
    page_title="Status Page",
    page_icon="📡",
    layout="centered"
)

st.markdown("""
<style>
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    
    .status-header {
        text-align: center;
        padding: 40px 0 20px;
    }
    .all-good {
        background: #ECFDF5;
        border: 1px solid #059669;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        margin: 20px 0;
    }
    .has-issues {
        background: #FEF2F2;
        border: 1px solid #DC2626;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        margin: 20px 0;
    }
    .monitor-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 0;
        border-bottom: 1px solid #F3F4F6;
    }
    .uptime-bar {
        display: flex;
        gap: 1px;
        height: 28px;
        border-radius: 4px;
        overflow: hidden;
        margin: 8px 0;
    }
    .uptime-segment {
        flex: 1;
        min-width: 3px;
    }
    .uptime-segment.up { background: #059669; }
    .uptime-segment.down { background: #DC2626; }
    .uptime-segment.unknown { background: #E5E7EB; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_supabase():
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


def get_uptime_bar_html(checks: list, days: int = 90):
    """Generate a 90-day uptime bar."""
    segments = 90  # One per day
    now = datetime.now(timezone.utc)
    
    html = '<div class="uptime-bar">'
    for i in range(segments):
        day_start = now - timedelta(days=segments - i)
        day_end = day_start + timedelta(days=1)
        
        day_checks = [c for c in checks
                     if day_start <= datetime.fromisoformat(
                         c["checked_at"].replace("Z", "+00:00")
                     ) < day_end]
        
        if not day_checks:
            css = "unknown"
        elif all(c["is_up"] for c in day_checks):
            css = "up"
        else:
            css = "down"
        
        html += f'<div class="uptime-segment {css}" title="{day_start.strftime("%b %d")}"></div>'
    
    html += '</div>'
    return html


def main():
    sb = get_supabase()
    if not sb:
        st.error("Status page not configured.")
        return
    
    slug = st.query_params.get("slug", "demo")
    
    # Look up status page
    try:
        page = sb.table("status_pages")\
            .select("*")\
            .eq("slug", slug)\
            .eq("is_public", True)\
            .single()\
            .execute()
    except Exception as e:
        page = None
        if slug != "demo":
            st.error(f"Could not load status page: {e}")
    
    if not page or not page.data:
        # No matching status page found — show a not-found message
        st.markdown("""
        <div class="status-header">
            <h1>📡 StatusPulse</h1>
            <p style="color: #6B7280;">Status Page Not Found</p>
        </div>
        """, unsafe_allow_html=True)
        st.info("The requested status page does not exist or is not public. Check the URL and try again.")
        st.markdown("""
        <div style="text-align:center; padding: 40px 0 20px; color: #9CA3AF; font-size: 0.8rem;">
            <p>Powered by <a href="https://hendrixaidev.github.io" target="_blank">StatusPulse</a> ⚡</p>
        </div>
        """, unsafe_allow_html=True)
        return
    else:
        # Configured status page
        st.markdown(f"""
        <div class="status-header">
            <h1>{page.data.get('title', 'Status Page')}</h1>
            <p style="color: #6B7280;">{page.data.get('description', '')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Get monitors for this page
        page_monitors = sb.table("status_page_monitors")\
            .select("monitor_id")\
            .eq("status_page_id", page.data["id"])\
            .order("display_order")\
            .execute()
        
        if not page_monitors.data:
            st.info("No monitors configured.")
            return
        
        monitor_ids = [pm["monitor_id"] for pm in page_monitors.data]
        monitors = sb.table("monitors")\
            .select("*")\
            .in_("id", monitor_ids)\
            .execute()
        
        monitor_list = monitors.data if monitors.data else []
    
    # Overall status
    all_up = all(m["current_status"] == "up" for m in monitor_list)
    any_unknown = any(m["current_status"] == "unknown" for m in monitor_list)
    
    if all_up:
        st.markdown("""
        <div class="all-good">
            <h2 style="color: #059669; margin: 0;">🟢 All Systems Operational</h2>
            <p style="color: #6B7280; margin: 8px 0 0;">Everything is running smoothly</p>
        </div>
        """, unsafe_allow_html=True)
    elif any_unknown:
        st.markdown("""
        <div style="background: #FFF7ED; border: 1px solid #D97706; border-radius: 12px; padding: 24px; text-align: center; margin: 20px 0;">
            <h2 style="color: #D97706; margin: 0;">⚪ Status Unknown</h2>
            <p style="color: #6B7280; margin: 8px 0 0;">Some monitors haven't reported yet</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="has-issues">
            <h2 style="color: #DC2626; margin: 0;">🔴 Service Disruption</h2>
            <p style="color: #6B7280; margin: 8px 0 0;">Some systems are experiencing issues</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Individual monitors
    st.markdown("### Services")
    
    for monitor in monitor_list:
        status = monitor["current_status"]
        emoji = "🟢" if status == "up" else "🔴" if status == "down" else "⚪"
        
        # Get recent checks for uptime bar
        since = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        try:
            checks = sb.table("checks")\
                .select("is_up,checked_at")\
                .eq("monitor_id", monitor["id"])\
                .gte("checked_at", since)\
                .order("checked_at")\
                .execute()
            check_data = checks.data or []
        except Exception:
            check_data = []
        
        # Calculate uptime
        if check_data:
            total = len(check_data)
            up = sum(1 for c in check_data if c["is_up"])
            uptime_pct = round((up / total) * 100, 2)
        else:
            uptime_pct = 100.0
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{emoji} {monitor['name']}**")
        with col2:
            color = "#059669" if uptime_pct >= 99.5 else "#D97706" if uptime_pct >= 95 else "#DC2626"
            st.markdown(f"<span style='color:{color};font-weight:700'>{uptime_pct}% uptime</span>", unsafe_allow_html=True)
        
        # Uptime bar
        if check_data:
            bar_html = get_uptime_bar_html(check_data)
            st.markdown(bar_html, unsafe_allow_html=True)
            st.caption("90-day history — green = operational, red = incident, gray = no data")
        
        st.markdown("---")
    
    # Recent incidents
    try:
        incidents = sb.table("incidents")\
            .select("*, monitors(name)")\
            .order("started_at", desc=True)\
            .limit(5)\
            .execute()
        
        if incidents.data:
            st.markdown("### Recent Incidents")
            for inc in incidents.data:
                resolved = "✅ Resolved" if inc["is_resolved"] else "🔴 Ongoing"
                name = inc.get("monitors", {}).get("name", "Unknown") if isinstance(inc.get("monitors"), dict) else "Monitor"
                duration = ""
                if inc.get("duration_seconds"):
                    mins = inc["duration_seconds"] // 60
                    duration = f" ({mins}m)"
                
                started = inc["started_at"][:16].replace("T", " ")
                st.markdown(f"- {resolved} **{name}** — {started} UTC{duration}")
    except Exception:
        pass  # Incidents section is non-critical; fail silently
    
    # Footer
    st.markdown("""
    <div style="text-align:center; padding: 40px 0 20px; color: #9CA3AF; font-size: 0.8rem;">
        <p>Powered by <a href="https://hendrixaidev.github.io" target="_blank">StatusPulse</a> ⚡</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
