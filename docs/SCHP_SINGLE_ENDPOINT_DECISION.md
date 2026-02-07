# SCHP Single-Endpoint Decision

**Date:** 2026-02-06  
**Decision Makers:** JJ (CEO), Hendrix (CTO)  
**Status:** Approved

---

## Decision

Adopt the **single-endpoint approach** for the StatusPulse Capability Health Protocol (SCHP).

Instead of requiring developers to create separate health endpoints per feature (`/health/ai`, `/health/db`, etc.), we will define a single unified endpoint:

```
GET /health/capabilities
```

---

## Specification

### Request
```http
GET /health/capabilities
```

### Response
```json
{
  "schp_version": "1.0",
  "app": "churnpilot",
  "status": "operational" | "degraded" | "down",
  "capabilities": {
    "<capability_name>": {
      "ok": boolean,
      "reason?": "quota_exhausted" | "api_down" | "rate_limited" | "maintenance",
      "degraded_since?": "2026-02-06T12:00:00Z",
      "eta?": "~2 hours" | "2026-02-06T14:00:00Z",
      "fallback?": "description of alternative"
    }
  }
}
```

### Example
```json
{
  "schp_version": "1.0",
  "app": "churnpilot",
  "status": "degraded",
  "capabilities": {
    "ai_extraction": {
      "ok": false,
      "reason": "quota_exhausted",
      "degraded_since": "2026-02-06T12:00:00Z",
      "fallback": "Use card library to find pre-existing cards"
    },
    "card_library": {
      "ok": true
    },
    "user_auth": {
      "ok": true
    },
    "spreadsheet_export": {
      "ok": false,
      "reason": "google_api_down",
      "eta": "~1 hour"
    }
  }
}
```

---

## Rationale

### Why Single Endpoint?

| Multiple Endpoints | Single Endpoint |
|---|---|
| Developer creates `/health/ai`, `/health/db`, `/health/payments`... | Developer creates one `/health/capabilities` |
| High friction per feature | Low friction, additive |
| StatusPulse must know all endpoint URLs | StatusPulse polls one URL |
| Authentication per endpoint | One authenticated call |

### Why App-Side (Approach #1)?

JJ identified that external testing (Approach #2) has authentication challenges:
- Features often require logged-in user context
- Internal functions may not be exposed externally
- Service accounts add customer burden

With app-side health reporting, the app tests *itself* with its own context.

---

## Implementation Phases

### Phase 1: Internal Dogfood (ChurnPilot ↔ StatusPulse)
- ChurnPilot implements `/health/capabilities`
- StatusPulse monitors it
- Webhook triggers on capability failure
- Validates the pattern works

### Phase 2: SDK Development
```python
# One-liner integration
from statuspulse import capabilities

capabilities.register("ai_extraction", check_fn=lambda: gemini.quota > 0)
capabilities.register("payments", check_fn=lambda: stripe.ping())

# Automatically exposes /health/capabilities
```

### Phase 3: Agentic Onboarding (Future)
- Customer provides URL + natural language description
- StatusPulse uses AI to discover test procedures
- Customer confirms monitoring setup
- No technical integration required

### Phase 4: Optional External Synthetic Testing
- For customers who can't implement the endpoint
- StatusPulse runs browser/API tests externally

---

## Standard Positioning

If adopted broadly, this becomes:
- **Like Stripe** for payments API patterns
- **Like OAuth** for auth patterns  
- **Like OpenAPI** for API documentation

We'd be defining the **capability health pattern** for SaaS.

---

## References

- Vision doc: `CAPABILITY_MONITORING_VISION.md`
- Discussion: Slack #jj-hendrix, 2026-02-06 ~21:00 PST
