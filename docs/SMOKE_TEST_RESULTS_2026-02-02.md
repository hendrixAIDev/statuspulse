# StatusPulse Smoke Test Results
**Date:** 2026-02-02  
**Tester:** Hendrix (Sub-agent)  
**Environment:** Local (localhost:8502)  
**Browser:** Chrome (openclaw profile)

---

## Test Results Summary
**Status:** ❌ BLOCKED - UNABLE TO COMPLETE  
**Tests Completed:** 0/5  
**Blockers:** Email validation + rate limiting preventing user registration

---

## Critical Blockers

### ❌ Blocker 1: Email Validation Rejecting Valid Emails
**Status:** CRITICAL BUG  
**Attempted Emails:**
1. `statuspulse.test20260202@test.com` → "Email address is invalid"
2. `test20260202@example.com` → "Email address is invalid"
3. `smoketest@test.com` → Triggered rate limit before validation could be tested

**Impact:** Cannot create test account to begin smoke testing

**Technical Notes:**
- All attempted emails are valid RFC 5322 format
- Error message: "Signup failed: Email address \"[email]\" is invalid"
- Suggests overly restrictive email validation regex or library configuration
- Need to investigate email validation implementation in signup flow

**Recommendation:**
- Check email validation regex/library
- Consider using standard Python `email-validator` library
- Add test coverage for various valid email formats
- Common pitfall: rejecting emails with numbers or multiple dots

---

### ❌ Blocker 2: Aggressive Rate Limiting on Signup
**Status:** CRITICAL - BLOCKS TESTING  
**Error:** "Signup failed: email rate limit exceeded"  
**Trigger:** 3 signup attempts within ~60 seconds

**Impact:** 
- Cannot test signup flow during development
- Cannot create multiple test accounts for testing
- Smoke testing blocked after 2-3 failed attempts

**Recommendations:**
1. **For Testing:** Add environment variable to disable rate limiting in local dev mode
2. **For Production:** Current rate limiting may be too aggressive
   - Consider: 5-10 signups per hour per IP for legitimate use cases
   - Add clear error message with time until reset
   - Implement per-IP vs global rate limiting

**Suggested Implementation:**
```python
# In app.py or signup handler
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"

if RATE_LIMIT_ENABLED and rate_limit_exceeded():
    show_error("Too many signup attempts. Please try again in X minutes.")
else:
    # Allow signup
```

---

## Test Plan (INCOMPLETE)

### Test 1: Register New Test User
**Status:** ❌ BLOCKED  
**Blocker:** Email validation + rate limiting  
**Attempts:** 3 (all failed)

---

### Test 2-5: Unable to Proceed
Cannot test monitor creation, editing, deletion, or database verification without a logged-in account.

---

## What Was Not Tested
Due to signup blockers, the following critical functionality remains untested:
1. ❌ Monitor creation flow
2. ❌ Monitor check execution
3. ❌ Database result verification
4. ❌ Monitor editing
5. ❌ Monitor deletion
6. ❌ Dashboard UX
7. ❌ Alert configuration
8. ❌ Session persistence
9. ❌ Logout flow

---

## UX Observations

### Positive
1. **Clean Landing Page:** Simple, focused design
2. **Clear Value Prop:** "Simple uptime monitoring for developers"
3. **Free Tier Visibility:** Prominently displays "3 monitors • 5-min checks • Email alerts"
4. **Tab Navigation:** Clear separation between Login and Sign Up

### Issues
1. **❌ CRITICAL: Email Validation Too Strict** - Rejecting valid emails
2. **❌ CRITICAL: Rate Limiting Too Aggressive** - Blocks legitimate testing/use
3. **No Error Context:** Rate limit error doesn't say when user can retry
4. **No Validation Feedback:** Doesn't explain what makes an email "invalid"

---

## Immediate Action Items

### P0 - Unblock Testing
1. **Fix email validation** to accept standard valid email formats
2. **Add dev mode flag** to disable rate limiting for local testing
3. **Create seed script** to generate test accounts for smoke testing

### P1 - Improve Signup UX
1. Add real-time email format validation with helpful hints
2. Show countdown timer when rate limited
3. Add password strength indicator
4. Consider "forgot password" flow

### P2 - Testing Infrastructure
1. Add E2E tests for signup flow with various email formats
2. Add rate limit bypass for automated testing
3. Document test account creation for manual QA

---

## Recommended Test Data Preparation

For future smoke tests, create a test account manually via database or admin panel:

```sql
-- Example seed user for testing
INSERT INTO users (email, display_name, password_hash, tier, created_at) 
VALUES (
  'smoketest@localhost',
  'Smoke Test User',
  '[bcrypt_hash_of_TestPass123!]',
  'free',
  NOW()
);
```

Then future tests can:
1. Log in with `smoketest@localhost` / `TestPass123!`
2. Create monitors
3. Test full workflow
4. Clean up test data

---

## Environment Details
- **Python:** 3.x (version TBD from project)
- **Streamlit:** (version TBD)
- **Database:** PostgreSQL (assumed based on schema.sql)
- **Session Management:** (unable to test)

---

## Comparison with ChurnPilot

| Feature | ChurnPilot | StatusPulse |
|---------|------------|-------------|
| **Signup** | ✅ Works | ❌ Blocked |
| **Email Validation** | ✅ Accepts valid emails | ❌ Rejects valid emails |
| **Rate Limiting** | ✅ Reasonable/none | ❌ Too aggressive |
| **Testability** | ✅ Can complete smoke tests | ❌ Blocked at signup |

---

## Next Steps
1. **Fix email validation bug** - P0
2. **Add rate limit bypass for dev** - P0
3. **Re-run complete smoke test suite** - After fixes
4. **Document test account setup** - For future testing
5. **Add automated E2E tests** - To catch these issues earlier

---

**Test Conclusion:** StatusPulse smoke testing blocked by critical bugs in signup flow. Unable to evaluate core monitoring functionality until authentication issues are resolved. Recommend fixing P0 blockers before considering this ready for preview or production deployment.

---

## Appendix: Attempted Workflow

```
1. Open localhost:8502 ✅
2. Click "Sign Up" tab ✅
3. Fill form:
   - Display Name: StatusPulse Test User ✅
   - Email: [multiple formats tried] ❌
   - Password: TestPass123! ✅
   - Confirm: TestPass123! ✅
4. Click "Create Account" ❌ → Email validation error
5. Retry with different email ❌ → Email validation error
6. Retry again ❌ → Rate limit error
7. BLOCKED - Cannot proceed
```
