# StatusPulse Code Review — Feb 1, 2026

## Files Reviewed
- `app.py` (main Streamlit dashboard)
- `monitor_engine.py` (monitoring engine)
- `public_status.py` (standalone public status page)
- `run_monitor.py` (daemon runner)
- `schema.sql` (database schema)
- `tests/test_monitor.py` (existing tests)

## Issues Found

### 🟡 Medium: `bcrypt` imported but never used in `app.py`
**Line:** `import bcrypt`
**Issue:** The import is present but auth is handled entirely by Supabase Auth. Unused dependency.
**Fix:** Remove the import and optionally remove from `requirements.txt` if not needed elsewhere.

### 🟡 Medium: `_send_webhook_alert` uses sync `httpx.post` in `monitor_engine.py`
**Issue:** The method imports `httpx` and calls `httpx.post()` synchronously. This works but is inconsistent with the async `check_url` pattern. In the Cloudflare Worker migration, this becomes `fetch()`.
**Fix:** Not urgent — Python daemon still works. Worker version already uses `fetch()`.

### 🟡 Medium: Subrequest limits on free Cloudflare tier
**Issue:** With 50 subrequest limit and ~3 per monitor, free tier maxes at ~16 monitors per cron run.
**Impact:** Free tier users with 3 monitors = 10 subrequests, well within limits. Only a concern if the platform grows.
**Fix:** Documented in migration plan. Paid tier ($5/mo) gives 1000 subrequests.

### 🟢 Low: No rate limiting on login attempts
**Issue:** `page_auth()` doesn't rate-limit login attempts. Could allow brute force.
**Impact:** Low — Supabase Auth has its own rate limiting.
**Fix:** Consider adding `st.session_state` counter for failed attempts.

### 🟢 Low: `public_status.py` demo mode exposes all monitors
**Issue:** When no slug matches, falls back to showing ALL active monitors from the system.
**Impact:** In production, this would expose all users' monitor names/URLs.
**Fix:** Remove demo mode fallback or restrict to a specific "demo" user's monitors.

### 🟢 Low: Exception handling in `public_status.py` is too broad
**Issue:** Multiple bare `except:` clauses silently swallow errors.
**Fix:** At minimum, catch specific exceptions and log errors.

### ✅ Good: Session management via `st.query_params`
Correctly follows the Streamlit session pattern (no localStorage/cookies).
Base64-encoded JSON token in URL param — simple and effective.

### ✅ Good: Cascade delete in `delete_monitor`
Properly cleans up checks, incidents, alert_configs, and alert_history before deleting the monitor.

### ✅ Good: Monitor check interval enforcement
`run_all_checks` correctly skips monitors that were recently checked.

### ✅ Good: Database schema
Well-structured with proper RLS policies, indexes, and triggers.
