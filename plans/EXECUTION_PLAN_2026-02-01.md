# StatusPulse — Execution Plan (Feb 1, 2026)

**Goal:** Deploy a trustworthy uptime monitoring service people actually rely on.  
**Success metric:** Active users with monitors configured, alerts triggered and received.  
**Note:** GitHub is down but development is NOT blocked. All testing runs against local server.

---

## Phase 1: Architecture Fix — Cloudflare Workers (~3-4 hours)

The Mac mini daemon is a prototype. For real users, monitoring must be:
- Distributed (multiple locations)
- Always-on (not dependent on our hardware)
- Fast (sub-second checks)

### 1.1 Cloudflare Workers migration
- [ ] Create Cloudflare account (free tier: 100K req/day, cron triggers)
- [ ] Build Worker script: fetch monitored URLs, store results in Supabase
- [ ] Set up Cron Triggers (every 5 min for free, every 1 min for pro)
- [ ] Test from multiple Cloudflare edge locations
- [ ] Retire Mac mini LaunchAgent (or keep as backup)

### 1.2 Alert system
- [ ] Verify email alerts work end-to-end (Gmail SMTP)
- [ ] Add webhook alerts (POST to user-specified URL)
- [ ] Test alert on status change (UP → DOWN and DOWN → UP)

---

## Phase 2: Test & Polish (~2 hours)

### 2.1 Tests
- [ ] Current 10 unit tests passing ✅
- [ ] Add tests for: alert delivery, public status page, auth flow
- [ ] Add E2E test against local Streamlit server: sign up → add monitor → verify dashboard renders

### 2.2 Smoke test (local server)
- [ ] Start local Streamlit server (`streamlit run app.py`)
- [ ] Browser automation walkthrough:
  - Sign up → Add monitor → View dashboard → Check status page
  - Test alert configuration
  - Mobile viewport check
- [ ] Fix any bugs found

### 2.3 UX
- [ ] Onboarding flow for new users
- [ ] Empty state when no monitors configured
- [ ] Mobile-friendly layout check
- [ ] Clear free tier limits (3 monitors, 5-min checks, 24h history)

---

## Phase 3: Public Status Pages (~2 hours)

Key differentiator — users can share their uptime with their own users.

- [ ] Public status page renders without auth (public_status.py)
- [ ] Shareable URL per user
- [ ] Shows: current status, uptime %, last 24h incident history
- [ ] Test locally

---

## Phase 4: Deploy & Verify Remote (when GitHub unblocks)

- [ ] Push code to GitHub/GitLab
- [ ] Deploy to Streamlit Cloud
- [ ] Claim statuspulse.streamlit.app
- [ ] Verify Supabase + Cloudflare Workers connection from cloud
- [ ] Smoke test against remote instance

---

## Phase 5: Distribution Prep (draft only — DO NOT POST until deployed)

- [ ] Draft Hacker News "Show HN" post
- [ ] Draft Reddit post for r/webdev, r/selfhosted
- [ ] Draft Dev.to article: "I built a free uptime monitor in a weekend"
- [ ] Prepare screenshots

---

## Execution Order

```
Phase 1 (Cloudflare Workers)
  → Phase 2 (tests + smoke test, local)
    → Phase 3 (public status pages, local)
      → Phase 4 (draft distribution)
        → [WAIT: GitHub recovery]
          → Phase 5 (deploy + remote smoke + launch)
```

## Open Questions
- Do we need a Cloudflare account? Can I create one under Hendrix's identity?
- Should we consider Vercel/Netlify cron as alternative to Cloudflare Workers?
- Public status pages: separate route in same Streamlit app, or separate deployment?
