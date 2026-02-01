"""
StatusPulse - Monitor Engine Tests
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

# Import the module under test
import sys
sys.path.insert(0, '..')
from monitor_engine import MonitorEngine


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "test-id"}])
    client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={"id": "mon-1", "name": "Test", "url": "https://example.com", "current_status": "unknown", "method": "GET", "expected_status": 200, "timeout_seconds": 30}
    )
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    return client


@pytest.fixture
def engine(mock_supabase):
    """Create a MonitorEngine with mocked Supabase."""
    return MonitorEngine(mock_supabase)


class TestCheckUrl:
    """Tests for URL checking functionality."""
    
    def test_check_url_success(self, engine):
        """Test successful URL check."""
        result = engine.run_check("https://httpbin.org/status/200", expected_status=200, timeout=10)
        assert result["is_up"] is True
        assert result["status_code"] == 200
        assert result["response_time_ms"] is not None
        assert result["response_time_ms"] > 0
        assert result["error_message"] is None
    
    def test_check_url_wrong_status(self, engine):
        """Test URL returning unexpected status."""
        result = engine.run_check("https://httpbin.org/status/404", expected_status=200, timeout=10)
        assert result["is_up"] is False
        assert result["status_code"] == 404
        assert "Expected 200" in result["error_message"]
    
    def test_check_url_timeout(self, engine):
        """Test URL that times out."""
        result = engine.run_check("https://httpbin.org/delay/5", timeout=1)
        assert result["is_up"] is False
        assert result["error_message"] is not None
    
    def test_check_url_invalid(self, engine):
        """Test invalid URL."""
        result = engine.run_check("https://this-domain-definitely-does-not-exist-xyz123.com", timeout=5)
        assert result["is_up"] is False
        assert result["error_message"] is not None
    
    def test_check_url_head_method(self, engine):
        """Test HEAD method check."""
        result = engine.run_check("https://httpbin.org/status/200", method="HEAD", expected_status=200, timeout=10)
        assert result["is_up"] is True
        assert result["status_code"] == 200


class TestSaveResults:
    """Tests for saving check results."""
    
    def test_save_check_result(self, engine, mock_supabase):
        """Test saving a check result to database."""
        result = {
            "status_code": 200,
            "response_time_ms": 150,
            "is_up": True,
            "error_message": None,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
        
        engine.save_check_result("monitor-123", result)
        
        mock_supabase.table.assert_called_with("checks")
        mock_supabase.table().insert.assert_called_once()
        
        inserted_data = mock_supabase.table().insert.call_args[0][0]
        assert inserted_data["monitor_id"] == "monitor-123"
        assert inserted_data["status_code"] == 200
        assert inserted_data["is_up"] is True


class TestStatusUpdate:
    """Tests for monitor status updates."""
    
    def test_update_status_up(self, engine, mock_supabase):
        """Test updating monitor status to up."""
        engine.update_monitor_status("mon-1", True)
        mock_supabase.table.assert_any_call("monitors")
    
    def test_update_status_down_creates_incident(self, engine, mock_supabase):
        """Test that going down creates an incident."""
        # Set current status to 'up' so transition to 'down' triggers incident
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"id": "mon-1", "name": "Test", "url": "https://example.com", "current_status": "up", "method": "GET"}
        )
        
        engine.update_monitor_status("mon-1", False)
        
        # Should have called table("incidents") to create an incident
        calls = [str(c) for c in mock_supabase.table.call_args_list]
        assert any("incidents" in c for c in calls)


class TestRunAllChecks:
    """Tests for the full monitoring cycle."""
    
    def test_run_all_checks_empty(self, engine, mock_supabase):
        """Test running checks with no monitors."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        results = engine.run_all_checks()
        assert results == []
    
    def test_run_all_checks_skips_recent(self, engine, mock_supabase):
        """Test that recently-checked monitors are skipped."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{
            "id": "mon-1",
            "name": "Test",
            "url": "https://example.com",
            "method": "GET",
            "expected_status": 200,
            "timeout_seconds": 30,
            "check_interval_seconds": 300,
            "is_active": True,
            "last_checked_at": datetime.now(timezone.utc).isoformat(),
            "current_status": "up"
        }])
        
        results = engine.run_all_checks()
        # Should skip because it was just checked
        assert len(results) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
