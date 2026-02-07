# StatusPulse: Capability Monitoring & Automated Remediation

**Created:** 2026-02-06  
**Status:** Vision / Parked for later implementation  
**Authors:** JJ (CEO), Hendrix (CTO)

---

## Executive Summary

Extend StatusPulse beyond binary uptime monitoring to **capability-aware health checks** with **automated remediation actions**. The key innovation is intent-based onboarding: customers describe what they want monitored in natural language, and StatusPulse (as an agent) figures out how to test it.

---

## The Problem

Traditional monitoring answers: "Is it up?"

But SaaS products degrade gracefully. A product can be "up" while critical features are broken:
- AI tokens exhausted → extraction fails
- Third-party API down → payments broken
- Database slow → timeouts on save

Users click buttons that don't work. They get cryptic errors. They churn.

---

## The Vision

### From Rules to Intent

**Traditional (LaunchDarkly, etc.):**
```
Customer writes: IF usage > quota THEN disable("feature_x")
```

**StatusPulse Vision:**
```
Customer says: "Check if the 'Extract Card' button works. 
               If it breaks, show users 'AI temporarily unavailable'."

StatusPulse: Creates test procedure, monitors, triggers action on failure.
```

### How It Works

```
┌─────────────────┐         ┌─────────────────┐
│   ChurnPilot    │         │   StatusPulse   │
│                 │         │                 │
│  /health/ai  ◄──┼─────────┼── polls 5min    │
│  returns state  │         │                 │
│                 │         │  detects:       │
│                 │         │  "quota_exhausted"
│                 │         │                 │
│  /hooks/degrade ◄─────────┼── triggers hook │
│  disables AI UI │         │                 │
│  shows message  │         │                 │
└─────────────────┘         └─────────────────┘
```

---

## Implementation Phases

### Phase 1: Internal Dogfood (This Week)

**ChurnPilot side:**
- Add `/health/ai-tokens` endpoint
- Returns: `{ "ok": true/false, "reason": "quota_exhausted" | null }`
- Add `/hooks/disable-ai` webhook endpoint
- When triggered: sets feature flag, shows graceful message to users

**StatusPulse side:**
- Add "Actions" to monitors (webhook URL + trigger conditions)
- When health check returns specific error, fire webhook
- Log action taken

**Success criteria:** ChurnPilot automatically disables AI extraction when tokens run out, before users hit the broken button.

### Phase 2: Agentic Onboarding (Future)

- Customer provides URL + natural language description
- StatusPulse uses AI/browser automation to discover test procedure
- Customer confirms: "Yes, monitor that"
- No technical setup required

### Phase 3: Public Feature (Future)

- Expose as StatusPulse Pro feature
- "Capability Monitoring + Auto-Remediation"
- Differentiator from basic uptime tools

---

## Competitive Landscape

| Product | What They Do | Gap |
|---------|--------------|-----|
| UptimeRobot | Up/down + webhooks | No semantic health, no remediation |
| Checkly | Programmable API checks | Requires code, no auto-remediation |
| LaunchDarkly | Feature flags | Manual triggers, not tied to health |
| PagerDuty | Incident automation | Human-in-loop, not autonomous |
| Kubernetes Probes | Readiness/liveness | Container-native only |

**Our position:** External circuit-breaker-as-a-service for SaaS, with intent-based onboarding.

---

## Technical Notes

### Health Endpoint Contract

```json
GET /health/{capability}

Response:
{
  "ok": boolean,
  "capability": "ai-extraction",
  "reason": "quota_exhausted" | "api_down" | "rate_limited" | null,
  "details": { ... },  // optional debugging info
  "degraded_since": "2026-02-06T12:00:00Z"  // optional
}
```

### Webhook Contract

```json
POST /hooks/{action}
Content-Type: application/json

{
  "source": "statuspulse",
  "monitor_id": "uuid",
  "capability": "ai-extraction",
  "reason": "quota_exhausted",
  "action": "disable",
  "timestamp": "2026-02-06T12:05:00Z"
}

Response: 200 OK
{
  "acknowledged": true,
  "action_taken": "disabled ai-extraction feature"
}
```

---

## Key Decision: Single-Endpoint Approach (2026-02-06)

**Approved.** See `SCHP_SINGLE_ENDPOINT_DECISION.md` for full rationale.

Instead of separate `/health/{capability}` endpoints, we use a single unified endpoint:

```
GET /health/capabilities → returns all capability states at once
```

This reduces developer friction and avoids authentication challenges with external testing.

---

## Open Questions (Parked)

1. ~~How does this extend to AI agents as consumers?~~ → Discussed. StatusPulse becomes "health signal layer for agents"
2. Should remediation be reversible automatically when health recovers?
3. How to handle flapping (rapid up/down cycles)?
4. Pricing model for this feature?

---

## Next Steps

See `ROADMAP.md` for full implementation phases.

- [ ] Implement Phase 1 for ChurnPilot ↔ StatusPulse
- [ ] Validate the pattern works internally
- [ ] Revisit for public release after dogfooding
