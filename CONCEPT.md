# StatusPulse — Simple Uptime Monitoring

## The Problem
Developers and small businesses need to know when their websites/APIs go down. Existing solutions are either too complex (Datadog, PagerDuty) or have annoying limits on free tiers (UptimeRobot's 50 monitor limit recently reduced).

## The Solution
StatusPulse: Dead-simple uptime monitoring with generous free tier and affordable Pro.

## Architecture

### Monitoring Engine (Cloudflare Workers)
- Cron Triggers run every 5 minutes
- Workers ping each monitored URL
- Check HTTP status, response time, SSL expiry
- Store results in Supabase
- Send alerts via email when status changes

### Database (Supabase)
- monitors table: URL, name, check_interval, expected_status
- checks table: timestamp, status_code, response_time_ms, error
- incidents table: start_time, end_time, duration, monitor_id
- users table: auth, plan, email preferences
- alerts table: type, destination, monitor_id

### Dashboard (Streamlit Cloud)
- Real-time status page
- Response time graphs
- Uptime percentage (30/60/90 day)
- Incident history
- Public status pages (share with users)

### Alerts
- Email (Gmail SMTP — free)
- Webhook (POST to any URL — free)
- Future: Slack, Discord, SMS

## Pricing

### Free Tier
- 3 monitors
- 5-minute check interval
- Email alerts
- 7-day history
- 1 public status page

### Pro ($9/month)
- Unlimited monitors
- 1-minute check interval
- Email + webhook alerts
- 90-day history
- Unlimited public status pages
- Custom domains for status pages
- Response time analytics

## Competitive Advantages
1. Truly generous free tier (not bait-and-switch)
2. Dead simple — no configuration bloat
3. Open source monitoring engine (builds trust)
4. AI-powered incident summaries (later, uses our Claude/Gemini)
5. Built by an AI — unique story for marketing

## Tech Stack
- **Monitoring:** Cloudflare Workers + Cron Triggers (free: 100K req/day)
- **Database:** Supabase (free: 500MB, 50K rows)
- **Dashboard:** Streamlit (free: Streamlit Cloud)
- **Auth:** Supabase Auth (free)
- **Alerts:** Gmail SMTP (free) + webhooks
- **Hosting cost:** $0/month

## MVP Scope (Tonight)
1. ✅ Supabase schema + project setup
2. ✅ Core monitoring script (Python, runs locally for now)
3. ✅ Streamlit dashboard with:
   - Add/remove monitors
   - Real-time status display
   - Response time chart
   - Uptime percentage
4. ✅ Email alerts on status change
5. ✅ Deploy to Streamlit Cloud

## Post-MVP (This Week)
- Cloudflare Workers migration (global monitoring)
- Public status pages
- Webhook alerts
- Pro tier with Stripe

## Revenue Projection
- Month 1: 50 free users, 5 Pro ($45/mo)
- Month 2: 200 free, 20 Pro ($180/mo)
- Month 3: 500 free, 50 Pro ($450/mo)

Even conservative: 20 Pro users = $180/mo = covers API costs + profit.
