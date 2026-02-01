# StatusPulse — Cloudflare Workers Migration Plan

## Why Migrate?

| Aspect | Mac mini Daemon | Cloudflare Workers |
|--------|-----------------|-------------------|
| **Availability** | Single point of failure | 300+ edge locations, 99.99% SLA |
| **Latency** | Checks from one location | Checks from nearest edge to target |
| **Maintenance** | LaunchAgent + cron management | Zero-ops, auto-scaling |
| **Cost** | $0 (existing hardware) | $0 (free tier) or $5/mo (paid) |
| **Reliability** | Down when Mac sleeps/reboots | Always-on |

## Cloudflare Workers Free Tier — What We Get

- **100,000 requests/day** (more than enough: 50 monitors × 288 checks/day = 14,400)
- **10ms CPU time per invocation** (our checks are mostly I/O wait, not CPU)
- **5 Cron Triggers per account** (we only need 1)
- **50 subrequests per invocation** (each check = 2 subrequests: fetch URL + save to Supabase)
  - ⚠️ This limits us to ~25 monitors per cron invocation on free tier
  - Workaround: batch monitors or upgrade to paid (1000 subrequests)
- **No charge for duration** (wall-clock time waiting for HTTP responses is free)

## Cloudflare Workers Paid Tier ($5/month)

- **10M requests/month included**
- **1000 subrequests per invocation** (supports 500 monitors per run)
- **15 min CPU time per cron invocation**
- **250 Cron Triggers**
- Enables 1-minute check intervals

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Cloudflare Workers                         │
│                                                               │
│  Cron Trigger (*/5 * * * *)                                  │
│       ↓                                                       │
│  scheduled() handler                                         │
│       ↓                                                       │
│  1. GET /rest/v1/monitors?is_active=eq.true → Supabase       │
│  2. For each due monitor:                                     │
│     a. fetch(monitor.url) → check result                     │
│     b. POST /rest/v1/checks → save result                    │
│     c. PATCH /rest/v1/monitors → update status               │
│     d. If status changed → create incident + send alerts     │
│  3. Log results                                               │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         ↕                          ↕
    ┌─────────┐              ┌────────────┐
    │ Supabase │              │ Target URLs │
    │ (data)   │              │ (monitored) │
    └─────────┘              └────────────┘
```

## Key Differences from Python Engine

1. **No SMTP from Workers** — Cloudflare Workers can't open TCP sockets for SMTP.
   - **Solution:** Use an email API service (Resend, Mailgun, SendGrid) via HTTP POST.
   - **Alternative:** Keep Mac mini daemon as email-only alert sender (reads alert_history, sends emails for unsent alerts).
   - **Recommended:** Migrate to Resend (free tier: 100 emails/day, perfect for alerts).

2. **No asyncio** — Workers use standard `fetch()` with `Promise.all()` for parallelism.

3. **Subrequest limits** — Free tier: 50/invocation. Each monitor needs ~3 subrequests (check URL + save result + update status). Max ~16 monitors on free tier.
   - **Mitigation:** Batch saves, use `Prefer: return=minimal` to reduce response parsing.

4. **CPU time limit** — 10ms on free tier sounds tight, but HTTP fetch wait time doesn't count as CPU time. Actual CPU work (JSON parsing, logic) is <1ms per monitor.

## Email Alert Migration Options

| Option | Cost | Complexity | Recommendation |
|--------|------|------------|----------------|
| **Resend** | Free (100/day) | Low (HTTP API) | ✅ Best for us |
| **Mailgun** | Free (100/day for 3 months) | Low | Good |
| **SendGrid** | Free (100/day) | Medium | Overkill |
| **Keep Mac mini for email** | $0 | Low | Fallback option |

### Resend Integration (Recommended)
```javascript
// Add to Worker
async function sendEmailViaResend(env, to, subject, html) {
  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      from: 'StatusPulse <alerts@statuspulse.dev>',
      to: [to],
      subject,
      html
    })
  });
}
```

## Setup Steps

### 1. Create Cloudflare Account
- Go to https://dash.cloudflare.com/sign-up
- Sign up with hendrix.ai.dev@gmail.com
- Free tier — no credit card required
- Verify email

### 2. Install Wrangler CLI
```bash
npm install -g wrangler
wrangler login  # Opens browser for OAuth
```

### 3. Configure Secrets
```bash
cd projects/statuspulse/worker
wrangler secret put SUPABASE_URL
# Paste: https://iwekqsxshzadzxezkrxo.supabase.co

wrangler secret put SUPABASE_SERVICE_KEY
# Paste: (service key from .env)
```

### 4. Deploy
```bash
cd projects/statuspulse/worker
npm install
wrangler deploy
```

### 5. Verify
```bash
# Check health endpoint
curl https://statuspulse-monitor.<account>.workers.dev/

# Test cron manually
curl http://localhost:8787/__scheduled?cron=*/5+*+*+*+*

# View live logs
wrangler tail
```

### 6. Retire Mac mini Daemon
Once Workers are confirmed stable (monitor for 24-48h):
```bash
launchctl unload ~/Library/LaunchAgents/com.statuspulse.monitor.plist
```
Keep the plist file as backup — can reactivate if Workers have issues.

## Testing Strategy

1. **Local dev:** `wrangler dev --test-scheduled` → hit `/__scheduled` endpoint
2. **Staging:** Deploy to staging environment, use test monitors
3. **Production:** Deploy with existing monitors, compare results with Mac mini daemon running in parallel
4. **Cutover:** After 24h of matching results, disable Mac mini daemon

## Subrequest Budget (Free Tier)

Per monitor check:
- 1 subrequest: `fetch(monitor.url)` — the actual check
- 1 subrequest: `POST /rest/v1/checks` — save result  
- 1 subrequest: `PATCH /rest/v1/monitors` — update status
- (conditional) 1 subrequest: incident creation
- (conditional) 1 subrequest: alert fetch
- (conditional) 1 subrequest: webhook POST

Typical: **3 subrequests/monitor** (no status change)
Worst case: **6 subrequests/monitor** (status change + webhook alert)

Free tier limit: 50 subrequests → **~16 monitors** safely

Initial getActiveMonitors call: **1 subrequest**

Total for 10 monitors: 1 + (10 × 3) = 31 subrequests ✅

## Cost Projections

| Scenario | Monitors | Check Interval | Monthly Requests | Cost |
|----------|----------|---------------|-----------------|------|
| Free tier | 10 | 5 min | ~90,000 | $0 |
| Free tier | 25 | 5 min | ~100,000 | $0 (at limit) |
| Paid | 50 | 5 min | ~450,000 | $5/mo |
| Paid | 100 | 1 min | ~4,500,000 | $5/mo |
| Paid | 500 | 1 min | ~22,500,000 | ~$8.75/mo |

## Files Created

- `worker/src/index.js` — Main Worker script (monitoring engine)
- `worker/wrangler.jsonc` — Wrangler configuration with cron triggers
- `worker/package.json` — Node.js package config

## Open Items

- [ ] Create Cloudflare account (hendrix.ai.dev@gmail.com)
- [ ] Set up Resend account for email alerts from Workers
- [ ] Deploy Worker
- [ ] Run parallel with Mac mini daemon for 24h validation
- [ ] Update Supabase RLS to allow Worker service key
- [ ] Consider custom domain for Worker (api.statuspulse.dev)
