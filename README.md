# CivicAlert 🏙️

A crowdsourced civic issue reporting and resolution system built with Flask.
Citizens report local problems (potholes, broken streetlights, garbage, etc.), officials manage and resolve them, and the community can track progress in real time.

Live at: **[bittyboomers.tech](https://bittyboomers.tech)**

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.14 + Flask |
| Database | PostgreSQL via [Neon](https://neon.tech) (cloud-hosted) |
| ORM | SQLAlchemy + Flask-Migrate |
| Auth | Flask-Login with email OTP verification |
| Email | Zoho Mail via Flask-Mail (`@bittyboomers.tech`) |
| Rate Limiting | Flask-Limiter |
| Hosting | Cloudflare Tunnel (on-demand, no VPS needed) |
| Domain | bittyboomers.tech via Cloudflare DNS |

---

## Features

### Citizen
- Register with email OTP verification
- Submit complaints with photo, map pin, address, and pincode
- Edit complaints while status is pending or acknowledged
- Track full status timeline with audit history
- Confirm or dispute resolution proof uploaded by officials
- Community feed filtered by ward, category, and status
- Upvote others' complaints (one vote per user)

### Official / Admin
- Dashboard with stats (total, pending, in progress, resolved, disputed)
- Filter, search, and paginate all complaints
- Update status with notes — emails citizen automatically
- Assign complaints to officials
- Upload resolution proof photo — notifies citizen to confirm
- User role management (citizen / official / admin)
- Analytics: by category, status, ward, average resolution time
- JSON API: `GET /admin/api/complaints`

---

## Project Structure

```
civic_alert/
├── app.py                  # Flask factory + config
├── extensions.py           # db, login_manager, mail, limiter, migrate
├── requirements.txt
├── models/
│   ├── user.py             # User model with email OTP verification
│   └── complaint.py        # Complaint, StatusHistory, UpvoteLog
├── routes/
│   ├── auth.py             # Register, verify OTP, login, logout
│   ├── complaints.py       # Submit, edit, detail, upvote, feed, confirm resolution
│   └── admin.py            # Admin dashboard, manage, assign, proof upload, analytics
├── services/
│   └── email.py            # All email notifications via Zoho Mail
└── templates/              # Jinja2 templates
```

---

## Roles

| Role | Access |
|---|---|
| citizen | Submit, edit (pending only), track own complaints, community feed |
| official | Everything citizen + full admin panel |
| admin | Everything official + user role management |

---

## Local Development Setup

### 1. Clone and set up environment

```bash
git clone https://github.com/IndiQuarks/civic_alert.git
cd civic_alert

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run locally with SQLite (zero config)

```bash
python app.py
# → http://localhost:5000
```

No database setup needed — SQLite is created automatically at `instance/civic.db`.

**Default admin login:** `admin@civic.gov.in` / `admin123`

### 3. Run with Neon PostgreSQL (production database)

```bash
export DATABASE_URL="postgresql+psycopg://user:password@host/dbname?sslmode=require&sslnegotiation=postgres"
python app.py
```

> **Note:** This project runs on Python 3.14. Use `psycopg` (psycopg3) not `psycopg2`. The connection string must include `sslnegotiation=postgres` for Neon compatibility on Python 3.14.

---

## Email Setup

Emails are sent from `noreply@bittyboomers.tech` via Zoho Mail SMTP.

```bash
export MAIL_USERNAME="noreply@bittyboomers.tech"
export MAIL_PASSWORD="your-zoho-app-password"
```

If these are not set, OTPs and notifications print to the terminal — useful for local dev.

**SMTP settings used:**
- Server: `smtp.zoho.in`
- Port: `587`
- TLS: Yes

---

## Deployment (Cloudflare Tunnel)

This app runs on-demand using a Cloudflare Tunnel — no VPS required. When `start.sh` is running, the site is live at `bittyboomers.tech`. When you shut it down, the site goes offline.

```bash
./start.sh     # goes live at bittyboomers.tech
# Ctrl+C to shut down
```

`start.sh` is not committed to this repo (it contains credentials). Create it locally:

```bash
cat > start.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting CivicAlert..."
source /path/to/venv/bin/activate
export DATABASE_URL="your-neon-url"
export MAIL_USERNAME="noreply@bittyboomers.tech"
export MAIL_PASSWORD="your-zoho-app-password"
python app.py &
FLASK_PID=$!
sleep 5
cloudflared tunnel run civicalert &
TUNNEL_PID=$!
echo "🎉 bittyboomers.tech is LIVE — Ctrl+C to shut down"
trap "kill $FLASK_PID $TUNNEL_PID; exit" SIGINT
wait
EOF
chmod +x start.sh
```

---

## Database Migrations

Flask-Migrate is set up for schema management.

```bash
# First time setup against a new database
flask --app app:create_app db init
flask --app app:create_app db migrate -m "initial schema"
flask --app app:create_app db upgrade

# After any model change
flask --app app:create_app db migrate -m "describe change"
flask --app app:create_app db upgrade
```

---

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | No (falls back to SQLite) |
| `MAIL_USERNAME` | Zoho mail address | No (prints to terminal) |
| `MAIL_PASSWORD` | Zoho App Password | No (prints to terminal) |
| `SECRET_KEY` | Flask session secret | No (insecure default used) |

---

## Known Constraints

- Uploaded complaint images are stored locally — they will not persist if the machine changes. Cloud storage (Cloudflare R2 or AWS S3) is the recommended upgrade path.
- The app runs in Flask's development server — fine for on-demand use, but swap to Gunicorn for a permanent VPS deployment.
- Rate limit counters are in-memory and reset on restart.
