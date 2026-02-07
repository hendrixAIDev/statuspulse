# StatusPulse Roadmap

**Last Updated:** 2026-02-06

---

## Vision

StatusPulse evolves from simple uptime monitoring to **the health signal layer for AI agents and SaaS applications**.

---

## Current Status

🟢 **MVP Live** — Basic uptime monitoring with email alerts  
📍 **URL:** statuspulse.streamlit.app

---

## Roadmap

### Phase 1: Capability Monitoring (Dogfood) ⬅️ NEXT
**Timeline:** Week of 2026-02-10  
**Objective:** Prove the SCHP pattern with ChurnPilot ↔ StatusPulse integration

**Deliverables:**
- [ ] ChurnPilot: Implement `/health/capabilities` endpoint
  - Report: `ai_extraction`, `card_library`, `user_auth` status
  - Return structured JSON per SCHP spec
- [ ] StatusPulse: Add "Capability Monitor" type (polls JSON endpoints)
- [ ] StatusPulse: Add "Actions" to monitors (webhook on specific failure)
- [ ] ChurnPilot: Implement `/hooks/disable-ai` webhook receiver
- [ ] End-to-end test: AI quota exhausted → StatusPulse detects → Webhook fires → ChurnPilot disables AI UI

**Decision:** Single-endpoint approach approved (see `docs/SCHP_SINGLE_ENDPOINT_DECISION.md`)

---

### Phase 2: StatusPulse Pro Feature
**Timeline:** After Phase 1 validated  
**Objective:** Expose capability monitoring as public feature

**Deliverables:**
- [ ] UI for configuring capability monitors
- [ ] Webhook action builder (URL + headers + body template)
- [ ] Per-capability alerting (not just down/up)
- [ ] History/timeline of capability state changes
- [ ] Public SCHP specification documentation

---

### Phase 3: SDK & Easy Integration
**Timeline:** TBD  
**Objective:** Make SCHP adoption frictionless

**Deliverables:**
- [ ] Python SDK: `statuspulse.capabilities.register()`
- [ ] Node.js SDK
- [ ] Auto-expose `/health/capabilities` via middleware
- [ ] One-liner integration guides

---

### Phase 4: Agentic Onboarding
**Timeline:** Future  
**Objective:** Zero-code capability monitoring setup

**Deliverables:**
- [ ] Customer provides URL + natural language description
- [ ] StatusPulse AI discovers test procedures
- [ ] Customer confirms: "Yes, monitor that"
- [ ] Browser automation for UI-based feature testing

---

### Phase 5: Health Signal Layer for AI Agents
**Timeline:** Future  
**Objective:** Become the "pre-flight check" for AI agents

**Deliverables:**
- [ ] Aggregated health API: `GET /api/health/all`
- [ ] Agent-optimized response format
- [ ] Cross-service health dashboard
- [ ] MCP server for agent integration

**Vision:** AI agents query StatusPulse before taking actions to know what's working.

---

## Strategic Context

- **Related Vision Doc:** `docs/CAPABILITY_MONITORING_VISION.md`
- **Single-Endpoint Decision:** `docs/SCHP_SINGLE_ENDPOINT_DECISION.md`
- **Target Market:** Indie SaaS builders, AI agent developers
- **Competitive Gap:** No external service does "circuit breaker as a service" for SaaS

---

## Backlog (Unprioritized)

- Multi-region monitoring
- Custom check scripts (headless browser)
- Slack/Discord alert channels
- Public status page generator
- Incident management integration (PagerDuty, OpsGenie)
