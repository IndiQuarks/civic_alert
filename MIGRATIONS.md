# Database Migration Guide — CivicAlert + Neon PostgreSQL

## Overview

This project uses **Flask-Migrate** (built on Alembic) for database schema management.
Every model change becomes a versioned migration file — you never delete data to update the schema.

- **Local dev** → SQLite (`instance/civic.db`) — zero setup, auto-used when `DATABASE_URL` is not set
- **Production (VPS)** → Neon PostgreSQL — set `DATABASE_URL` as an environment variable

---

## One-Time Setup (Run Once, On Your Laptop)

### 1. Activate your virtual environment

```bash
cd civic_alert_v2
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Point to your Neon database

```bash
export DATABASE_URL="postgresql://neondb_owner:YOUR_PASSWORD@ep-broad-fire-a1niym4m-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
```

Replace `YOUR_PASSWORD` with your actual Neon password.

### 3. Initialise Flask-Migrate

```bash
flask --app app:create_app db init
```

This creates a `migrations/` folder in your project. **Commit this folder to git** — it's not a secret.

### 4. Generate the initial migration from your models

```bash
flask --app app:create_app db migrate -m "initial schema"
```

This auto-generates a migration file in `migrations/versions/`. Open it and check it looks right — it should list all your tables: `users`, `complaints`, `status_history`, `upvote_log`.

### 5. Apply the migration to Neon

```bash
flask --app app:create_app db upgrade
```

This creates all your tables in the Neon database. You'll see output like:
```
INFO  [alembic.runtime.migration] Running upgrade  -> abc123def456, initial schema
```

Your Neon database is now ready. ✅

---

## Workflow for Every Future Model Change

Whenever you edit a model (add a column, rename a field, add a new table):

```bash
# 1. Make your changes to models/*.py

# 2. Generate a migration
flask --app app:create_app db migrate -m "describe what changed"

# 3. Review the generated file in migrations/versions/

# 4. Apply it locally (SQLite)
flask --app app:create_app db upgrade

# 5. On the VPS, pull the new code and run:
flask --app app:create_app db upgrade
```

You **never** need to delete the database to apply schema changes.

---

## Running Locally (SQLite, No DATABASE_URL Needed)

```bash
# First time only — no DATABASE_URL needed for local dev
flask --app app:create_app db upgrade   # creates SQLite tables from migrations
python app.py
```

For subsequent runs, just `python app.py` — the database already exists.

---

## VPS Setup (Systemd Service)

In your `/etc/systemd/system/civicalert.service` file, add the `DATABASE_URL` environment variable:

```ini
[Service]
...
Environment="DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@ep-broad-fire-a1niym4m-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
Environment="MAIL_USERNAME=your-email@gmail.com"
Environment="MAIL_PASSWORD=your-app-password"
```

After deploying new code to the VPS, always run migrations before restarting the service:

```bash
source /home/civic/civicalert/venv/bin/activate
export DATABASE_URL="your-neon-url"
flask --app app:create_app db upgrade
sudo systemctl restart civicalert
```

---

## Viewing Your Data

You can connect to your Neon database with any PostgreSQL GUI:

**TablePlus** (Mac/Windows/Linux, free tier)
1. New connection → PostgreSQL
2. Paste your full Neon connection string into the URL field
3. Connect — you'll see all tables and can browse/edit data

**pgAdmin** (free, open source)
1. Add Server → paste host, port (5432), database name, username, password from your Neon connection string
2. Full GUI for queries, table inspection, backups

**psql (terminal)**
```bash
psql "postgresql://neondb_owner:YOUR_PASSWORD@ep-broad-fire-a1niym4m-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
```

---

## Neon Dashboard

Log in at [console.neon.tech](https://console.neon.tech) to:
- View database size and connection count
- Browse tables with the built-in SQL editor
- Set up automatic backups and branching
- Reset your password if credentials are compromised
