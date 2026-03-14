# CivicAlert – SIH25031
### Crowdsourced Civic Issue Reporting & Resolution System

---

## Quick Start

```bash
pip install -r requirements.txt

# Set email credentials (Gmail App Password)
export MAIL_USERNAME="project.career2@gmail.com"
export MAIL_PASSWORD="your-app-password-here"

python app.py
# → http://localhost:5000
```

**Default admin login:** `admin@civic.gov.in` / `admin123`

---

## Email Setup (Gmail)

1. Go to **myaccount.google.com → Security → 2-Step Verification → App passwords**
2. Generate a new App Password (select "Mail")
3. Copy the 16-character password
4. Set environment variables:

```bash
# Linux / Mac
export MAIL_USERNAME="project.career2@gmail.com"
export MAIL_PASSWORD="xxxx xxxx xxxx xxxx"

# Windows CMD
set MAIL_USERNAME=project.career2@gmail.com
set MAIL_PASSWORD=xxxx xxxx xxxx xxxx

# Windows PowerShell
$env:MAIL_USERNAME="project.career2@gmail.com"
$env:MAIL_PASSWORD="xxxx xxxx xxxx xxxx"
```

**Dev mode (no credentials set):** All emails are printed to the terminal console — OTPs will appear there so you can test without setting up email.

---

## Features

### Citizen
- Register → Email OTP verification → Login
- Submit complaint with photo, map pin, pincode lookup, EXIF GPS extraction
- Edit complaints while status is pending/acknowledged
- Track full status timeline
- Confirm or dispute resolution proof uploaded by officials
- Community feed filtered by ward/category/status
- Upvote others' complaints

### Admin / Official
- Dashboard with stats (total, pending, in progress, resolved, disputed)
- Filter/search/paginate all complaints
- Update status with notes (emails citizen automatically)
- Assign to officials
- Upload resolution proof photo (emails citizen to confirm)
- User role management
- Analytics: by category, status, ward, avg resolution time
- JSON API: `GET /admin/api/complaints`

---

## Email Notifications Sent Automatically
| Event | Who gets emailed |
|---|---|
| Complaint submitted | Citizen |
| Status changes (any) | Citizen |
| Resolution proof uploaded | Citizen |
| OTP on registration | Citizen |

---

## Project Structure
```
civic_app/
├── app.py                  # Flask factory + email config
├── extensions.py           # db, login_manager, mail
├── requirements.txt
├── models/
│   ├── user.py             # User + OTP fields
│   └── complaint.py        # Complaint + StatusHistory + resolution proof
├── routes/
│   ├── auth.py             # Register, verify OTP, login, logout
│   ├── complaints.py       # Submit, edit, detail, upvote, feed, confirm resolution
│   └── admin.py            # Admin dashboard, manage, assign, proof upload, analytics
├── services/
│   └── email.py            # All email notifications (Flask-Mail)
└── templates/              # 14 Jinja2 templates
```

---

## Roles
| Role | Access |
|---|---|
| citizen | Submit, edit (pending only), track own complaints, community feed |
| official | Everything citizen + full admin panel |
| admin | Everything official + user role management |
