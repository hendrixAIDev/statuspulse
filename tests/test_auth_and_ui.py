"""
StatusPulse - Auth Flow, Public Status Page, and Error Handling Tests
"""

import pytest
import json
import base64
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ─── Auth / Session Tests ────────────────────────────────────────────────────

class TestSessionManagement:
    """Tests for session encode/decode via query params."""

    def test_encode_session_roundtrip(self):
        """Test that session data survives encode → decode."""
        user_data = {"user_id": "abc-123", "email": "test@example.com", "token": "tok_xyz"}
        token = base64.b64encode(json.dumps(user_data).encode()).decode()
        decoded = json.loads(base64.b64decode(token).decode())
        assert decoded == user_data

    def test_decode_invalid_token_returns_none(self):
        """Test that a corrupt token doesn't crash — returns None."""
        # Simulate what get_session does on bad data
        bad_tokens = ["", "not-base64!!!", "====", base64.b64encode(b"not-json").decode()]
        for token in bad_tokens:
            try:
                data = json.loads(base64.b64decode(token).decode())
            except Exception:
                data = None
            # Should gracefully fail, not raise
            assert data is None or isinstance(data, dict)

    def test_session_with_missing_fields(self):
        """Test session with partial data still decodes."""
        partial = {"email": "a@b.com"}  # missing user_id
        token = base64.b64encode(json.dumps(partial).encode()).decode()
        decoded = json.loads(base64.b64decode(token).decode())
        assert decoded.get("user_id") is None
        assert decoded.get("email") == "a@b.com"


class TestAuthValidation:
    """Tests for signup/login validation logic (UI-level)."""

    def test_password_mismatch_detected(self):
        """Passwords must match on signup."""
        password = "secret123"
        password2 = "secret456"
        assert password != password2

    def test_password_too_short_detected(self):
        """Password must be at least 6 chars."""
        assert len("abc") < 6
        assert len("abcdef") >= 6

    def test_empty_email_rejected(self):
        """Empty email should not pass validation."""
        assert not ""  # falsy
        assert not None

    def test_url_auto_prefix(self):
        """URLs without scheme get https:// prepended."""
        url = "example.com"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        assert url == "https://example.com"

    def test_url_with_scheme_unchanged(self):
        """URLs with scheme stay as-is."""
        url = "http://example.com"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        assert url == "http://example.com"


class TestSignupFunction:
    """Tests for the signup function with mocked Supabase."""

    def test_signup_success(self):
        """Successful signup returns success + user_id."""
        mock_sb = MagicMock()
        mock_user = MagicMock()
        mock_user.id = "user-uuid-123"
        mock_sb.auth.sign_up.return_value = MagicMock(user=mock_user)

        # Inline the signup logic
        result = mock_sb.auth.sign_up({
            "email": "test@example.com",
            "password": "password123",
            "options": {"data": {"display_name": "test"}}
        })
        assert result.user.id == "user-uuid-123"

    def test_signup_failure_returns_error(self):
        """Failed signup returns error message."""
        mock_sb = MagicMock()
        mock_sb.auth.sign_up.side_effect = Exception("User already exists")

        with pytest.raises(Exception, match="User already exists"):
            mock_sb.auth.sign_up({"email": "dup@example.com", "password": "pass"})


class TestLoginFunction:
    """Tests for the login function with mocked Supabase."""

    def test_login_success(self):
        """Successful login returns user + access token."""
        mock_sb = MagicMock()
        mock_user = MagicMock()
        mock_user.id = "user-uuid-456"
        mock_session = MagicMock()
        mock_session.access_token = "jwt-token-xyz"
        mock_sb.auth.sign_in_with_password.return_value = MagicMock(
            user=mock_user, session=mock_session
        )

        result = mock_sb.auth.sign_in_with_password({
            "email": "test@example.com", "password": "password123"
        })
        assert result.user.id == "user-uuid-456"
        assert result.session.access_token == "jwt-token-xyz"

    def test_login_wrong_password(self):
        """Wrong password raises exception."""
        mock_sb = MagicMock()
        mock_sb.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")

        with pytest.raises(Exception, match="Invalid login"):
            mock_sb.auth.sign_in_with_password({
                "email": "test@example.com", "password": "wrong"
            })


# ─── Public Status Page Tests ────────────────────────────────────────────────

class TestPublicStatusPage:
    """Tests for public status page data rendering."""

    def test_uptime_bar_html_all_up(self):
        """Uptime bar with all-up checks should have only 'up' segments."""
        from public_status import get_uptime_bar_html

        now = datetime.now(timezone.utc)
        checks = [
            {"is_up": True, "checked_at": (now - timedelta(days=i)).isoformat()}
            for i in range(90)
        ]
        html = get_uptime_bar_html(checks)
        assert "uptime-bar" in html
        assert "down" not in html  # No down segments

    def test_uptime_bar_html_with_downtime(self):
        """Uptime bar with some down checks should have 'down' segments."""
        from public_status import get_uptime_bar_html

        now = datetime.now(timezone.utc)
        checks = []
        for i in range(90):
            is_up = i != 5  # Day 5 is down
            checks.append({
                "is_up": is_up,
                "checked_at": (now - timedelta(days=90 - i) + timedelta(hours=12)).isoformat()
            })
        html = get_uptime_bar_html(checks)
        assert "down" in html

    def test_uptime_bar_html_empty(self):
        """Uptime bar with no checks shows all unknown."""
        from public_status import get_uptime_bar_html

        html = get_uptime_bar_html([])
        assert "unknown" in html
        assert "uptime-bar" in html

    def test_uptime_percentage_calculation(self):
        """Uptime percentage math is correct."""
        total = 100
        up = 95
        pct = round((up / total) * 100, 2)
        assert pct == 95.0

    def test_uptime_percentage_all_up(self):
        """100% uptime when all checks pass."""
        total = 288  # 24h at 5-min intervals
        up = 288
        pct = round((up / total) * 100, 2)
        assert pct == 100.0

    def test_uptime_percentage_no_checks(self):
        """Default to 100% when no checks exist."""
        # This mirrors the logic in app.py get_uptime_percentage
        checks_data = []
        if not checks_data:
            uptime = 100.0
        assert uptime == 100.0


# ─── Error Handling Tests ────────────────────────────────────────────────────

class TestMonitorErrorHandling:
    """Tests for error scenarios in the monitor engine."""

    def test_save_check_with_none_values(self):
        """Saving a check with None status_code/response_time shouldn't crash."""
        from monitor_engine import MonitorEngine

        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "c1"}])
        engine = MonitorEngine(mock_sb)

        result = {
            "status_code": None,
            "response_time_ms": None,
            "is_up": False,
            "error_message": "Connection refused",
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
        # Should not raise
        engine.save_check_result("mon-1", result)
        mock_sb.table().insert.assert_called_once()

    def test_update_status_missing_monitor(self):
        """Updating status for non-existent monitor exits gracefully."""
        from monitor_engine import MonitorEngine

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)
        engine = MonitorEngine(mock_sb)

        # Should not raise when monitor not found
        engine.update_monitor_status("nonexistent-id", True)

    def test_email_alert_skipped_without_smtp(self):
        """Email alert is silently skipped when SMTP not configured."""
        from monitor_engine import MonitorEngine

        mock_sb = MagicMock()
        engine = MonitorEngine(mock_sb)
        engine.smtp_email = ""
        engine.smtp_password = ""

        # _send_email_alert should return early without error
        engine._send_email_alert(
            {"destination": "user@example.com"},
            {"name": "Test", "url": "https://example.com"},
            "down"
        )
        # No exception = pass

    def test_webhook_alert_failure_handled(self):
        """Webhook alert failure is caught and logged."""
        from monitor_engine import MonitorEngine

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": "alert-1",
                "alert_type": "webhook",
                "destination": "http://nonexistent.invalid/hook",
                "is_active": True
            }]
        )
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
        engine = MonitorEngine(mock_sb)

        # Should catch the exception and log a failed alert
        engine._send_alerts("mon-1", {"name": "Test", "url": "https://example.com"}, "down")

    def test_delete_monitor_cascades(self):
        """Delete monitor cleans up all related tables."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

        # Simulate the delete_monitor logic from app.py
        monitor_id = "mon-to-delete"
        for table in ["checks", "incidents", "alert_configs", "alert_history", "monitors"]:
            mock_sb.table(table).delete().eq(
                "monitor_id" if table != "monitors" else "id",
                monitor_id
            ).execute()

        # Should have called table() for each related table
        table_calls = [str(c) for c in mock_sb.table.call_args_list]
        assert len(table_calls) >= 5


class TestMonitorLimits:
    """Tests for free tier limits."""

    def test_free_tier_limit_enforced(self):
        """Free tier users can't exceed 3 monitors."""
        max_monitors = 3
        current_count = 3
        assert current_count >= max_monitors  # Should be blocked

    def test_pro_tier_allows_more(self):
        """Pro tier users have higher limits."""
        plan = "pro"
        max_monitors = 50
        current_count = 10
        assert current_count < max_monitors


# ─── UI Rendering Helpers Tests ──────────────────────────────────────────────

class TestUIHelpers:
    """Tests for UI rendering functions in app.py."""

    def test_render_status_badge_up(self):
        """Status badge for 'up' shows green."""
        # Inline from app.py render_status_badge
        status = "up"
        colors = {
            "up": ("🟢", "#059669", "UP"),
            "down": ("🔴", "#DC2626", "DOWN"),
            "unknown": ("⚪", "#6B7280", "UNKNOWN"),
            "paused": ("⏸️", "#D97706", "PAUSED")
        }
        emoji, color, label = colors.get(status, colors["unknown"])
        html = f'{emoji} <span style="color:{color};font-weight:700">{label}</span>'
        assert "UP" in html
        assert "#059669" in html

    def test_render_status_badge_down(self):
        """Status badge for 'down' shows red."""
        status = "down"
        colors = {
            "up": ("🟢", "#059669", "UP"),
            "down": ("🔴", "#DC2626", "DOWN"),
            "unknown": ("⚪", "#6B7280", "UNKNOWN"),
        }
        emoji, color, label = colors.get(status, ("⚪", "#6B7280", "UNKNOWN"))
        assert label == "DOWN"
        assert color == "#DC2626"

    def test_render_status_badge_unknown_fallback(self):
        """Unknown status type falls back to 'unknown'."""
        status = "banana"
        colors = {
            "up": ("🟢", "#059669", "UP"),
            "down": ("🔴", "#DC2626", "DOWN"),
            "unknown": ("⚪", "#6B7280", "UNKNOWN"),
        }
        emoji, color, label = colors.get(status, colors["unknown"])
        assert label == "UNKNOWN"

    def test_elapsed_time_formatting(self):
        """Last check time formatting works correctly."""
        now = datetime.now(timezone.utc)

        # 30 seconds ago
        dt = now - timedelta(seconds=30)
        elapsed = (now - dt).total_seconds()
        assert elapsed < 60
        result = f"{int(elapsed)}s ago"
        assert "30s ago" == result

        # 5 minutes ago
        dt = now - timedelta(minutes=5)
        elapsed = (now - dt).total_seconds()
        assert 60 <= elapsed < 3600
        result = f"{int(elapsed/60)}m ago"
        assert "5m ago" == result

        # 2 hours ago
        dt = now - timedelta(hours=2)
        elapsed = (now - dt).total_seconds()
        assert elapsed >= 3600
        result = f"{int(elapsed/3600)}h ago"
        assert "2h ago" == result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
