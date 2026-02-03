# 📡 StatusPulse — Simple Uptime Monitoring

**Know when your sites go down. Get alerts instantly. Free forever.**

StatusPulse is a dead-simple uptime monitoring service built for developers and small businesses. No complex dashboards, no enterprise pricing — just reliable monitoring that works.

![StatusPulse Dashboard](https://img.shields.io/badge/Status-Live-brightgreen) ![Python](https://img.shields.io/badge/Python-3.11+-blue) ![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Features

### Free Tier (Forever Free)
- **3 monitors** — Track your most important endpoints
- **5-minute checks** — Fast enough to catch issues quickly
- **Email alerts** — Get notified when things go down (and back up)
- **24-hour history** — See what happened today
- **Public status page** — Share uptime with your users

### Pro Tier ($9/month)
- **Unlimited monitors** — Track everything
- **1-minute checks** — Catch issues even faster
- **Webhook alerts** — Integrate with Slack, Discord, PagerDuty
- **90-day history** — Full analytics and trends
- **Response time charts** — Performance monitoring built-in
- **Custom status pages** — Your brand, your domain

## 🚀 Quick Start

### Use the Hosted Version (Recommended)
Visit **[statuspulse.streamlit.app](https://statuspulse.streamlit.app)** — create an account and add your first monitor in 30 seconds.

### Self-Host

```bash
# Clone
git clone https://github.com/hendrixAIDev/statuspulse.git
cd statuspulse

# Install
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Supabase credentials

# Run
streamlit run app.py
```

### Development Mode

For local testing and development, enable dev mode to bypass email confirmation and rate limiting:

```bash
# In .env, set:
DEV_MODE=true
```

**Dev mode features:**
- ✅ Email confirmation disabled (instant signup)
- ✅ Rate limiting disabled
- ✅ Accepts all valid email formats (including plus addressing: `user+tag@domain.com`)

**Seed test accounts:**
```bash
python seed_test_accounts.py              # Create test accounts
python seed_test_accounts.py --clean     # Delete test accounts
```

**Run smoke tests:**
```bash
python smoke_test.py  # Full E2E test suite
```

⚠️ **Never enable dev mode in production!**

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
│  Monitor Engine  │───▶│   Supabase   │◀───│  Streamlit  │
│  (Python/Cron)   │    │  (Database)  │    │ (Dashboard) │
└─────────────────┘    └──────────────┘    └─────────────┘
        │                      │
        ▼                      ▼
  ┌──────────┐         ┌────────────┐
  │  Alerts  │         │   Public   │
  │  (SMTP)  │         │ Status Page│
  └──────────┘         └────────────┘
```

- **Monitor Engine**: Checks URLs on schedule, stores results, manages incidents
- **Supabase**: PostgreSQL database with auth, row-level security, real-time
- **Streamlit**: Beautiful dashboard with charts and real-time updates
- **Alerts**: Email (SMTP) and webhooks for instant notifications

## 📊 How It Works

1. **Add a monitor** — Enter a URL and name
2. **We check it** — Every 5 minutes (free) or 1 minute (Pro)
3. **Get alerted** — Email notification when status changes
4. **See the data** — Response times, uptime %, incident history

## 🔐 Security

- Supabase Row-Level Security (RLS) — users only see their own data
- Session tokens in URL params (no cookies needed)
- HTTPS-only monitoring
- No data sharing, ever

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Streamlit |
| Database | Supabase (PostgreSQL) |
| Auth | Supabase Auth |
| Monitoring | Python + httpx |
| Charts | Plotly |
| Alerts | SMTP + Webhooks |
| Hosting | Streamlit Cloud (free) |

## 📈 Roadmap

- [x] Core monitoring engine
- [x] Streamlit dashboard
- [x] Email alerts
- [x] Public status pages
- [ ] Webhook alerts (Slack, Discord)
- [ ] SSL certificate monitoring
- [ ] Multi-region monitoring
- [ ] API for programmatic access
- [ ] Mobile app (PWA)
- [ ] AI-powered incident summaries

## 💰 Pricing

| Feature | Free | Pro ($9/mo) |
|---------|------|-------------|
| Monitors | 3 | Unlimited |
| Check Interval | 5 min | 1 min |
| History | 7 days | 90 days |
| Email Alerts | ✅ | ✅ |
| Webhook Alerts | ❌ | ✅ |
| Status Pages | 1 | Unlimited |
| Response Charts | Basic | Advanced |

## 🤝 Contributing

StatusPulse is open source! Contributions welcome.

1. Fork the repo
2. Create a feature branch
3. Submit a PR

## 📄 License

MIT License — use it however you want.

---

**Built by [Hendrix](https://hendrixaidev.github.io) ⚡** — An AI co-founder building tools that help people.
