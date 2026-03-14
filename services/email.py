"""
Email notification service.
Uses Flask-Mail. Configure via env vars:
  MAIL_USERNAME=you@gmail.com
  MAIL_PASSWORD=your-app-password   (Gmail App Password)

Dev mode: if MAIL_USERNAME is unset, all emails are printed to the console.
"""
from flask import current_app
from flask_mail import Message
from extensions import mail


def _send(to_email: str, subject: str, html_body: str):
    """Fire-and-forget send. Never raises - logs on error."""
    try:
        username = current_app.config.get('MAIL_USERNAME', '')
        if not username:
            # Dev fallback: print to console so developers can see emails
            print(f'\n{"="*60}')
            print(f'📧 DEV EMAIL (not sent – set MAIL_USERNAME to enable)')
            print(f'   To:      {to_email}')
            print(f'   Subject: {subject}')
            print(f'{"="*60}\n')
            current_app.logger.info(f'[MAIL-DEV] To:{to_email} | {subject}')
            return
        msg = Message(subject=subject, recipients=[to_email], html=html_body)
        mail.send(msg)
        current_app.logger.info(f'[MAIL-SENT] To:{to_email} | {subject}')
    except Exception as exc:
        current_app.logger.error(f'[MAIL-ERROR] {exc}')


def _html(body_content: str, title: str, accent: str = '#3C887E') -> str:
    """Wrap content in a simple responsive email shell."""
    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  body {{font-family:Arial,sans-serif;background:#f4faf7;margin:0;padding:20px}}
  .wrap {{max-width:520px;margin:0 auto;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.08)}}
  .header {{background:{accent};padding:24px 28px;color:#fff}}
  .header h1 {{margin:0;font-size:1.2rem;font-weight:700}}
  .body {{padding:28px}}
  .body p {{color:#374151;line-height:1.6;margin:0 0 12px}}
  .info-row {{display:flex;gap:8px;padding:8px 0;border-bottom:1px solid #e8f5ee}}
  .info-label {{color:#6b7280;font-size:.85rem;min-width:130px}}
  .info-val {{color:#111827;font-size:.85rem;font-weight:600}}
  .otp-box {{background:#E0F2E9;border-radius:10px;padding:20px;text-align:center;margin:16px 0}}
  .otp-code {{font-size:2.5rem;font-weight:700;letter-spacing:12px;color:#3C887E}}
  .status-badge {{display:inline-block;padding:4px 12px;border-radius:20px;font-size:.8rem;font-weight:700;background:{accent};color:#fff}}
  .footer {{background:#f4faf7;padding:16px 28px;text-align:center;color:#9ca3af;font-size:.78rem}}
</style></head><body>
<div class="wrap">
  <div class="header"><h1>🏙️ CivicAlert</h1><p style="margin:4px 0 0;font-size:.85rem;opacity:.85">{title}</p></div>
  <div class="body">{body_content}</div>
  <div class="footer">CivicAlert · Smart India Hackathon 2025 · SIH25031<br>This is an automated message, please do not reply.</div>
</div></body></html>"""


# ── Public notification functions ─────────────────────────────────────────────

def send_complaint_submitted(complaint):
    user = complaint.reporter
    if not user: return
    body = f"""
<p>Hi <strong>{user.name}</strong>,</p>
<p>Your complaint has been successfully registered on CivicAlert. Here are the details:</p>
<div style="background:#f4faf7;border-radius:10px;padding:16px;margin:12px 0">
  <div class="info-row"><span class="info-label">Complaint ID</span><span class="info-val">#{complaint.id}</span></div>
  <div class="info-row"><span class="info-label">Title</span><span class="info-val">{complaint.title}</span></div>
  <div class="info-row"><span class="info-label">Category</span><span class="info-val">{complaint.category}</span></div>
  <div class="info-row"><span class="info-label">Priority</span><span class="info-val">{complaint.priority.upper()}</span></div>
  <div class="info-row" style="border:none"><span class="info-label">Location</span><span class="info-val">{complaint.address}</span></div>
</div>
<p>You will receive an email whenever the status of your complaint is updated by officials.</p>"""
    _send(user.email,
          f'[CivicAlert] Complaint #{complaint.id} Received',
          _html(body, f'Complaint #{complaint.id} Submitted'))


def send_status_changed(complaint, old_status: str, new_status: str, note: str = '', remarks: str = ''):
    user = complaint.reporter
    if not user: return
    color_map = {
        'pending': '#6c757d', 'acknowledged': '#5B7B7A',
        'in_progress': '#e67e22', 'resolved': '#3C887E',
        'rejected': '#c0392b', 'disputed': '#c0392b',
    }
    accent = color_map.get(new_status, '#3C887E')
    old_label = old_status.replace('_', ' ').title()
    new_label = new_status.replace('_', ' ').title()
    extra = ''
    if note:    extra += f'<div class="info-row"><span class="info-label">Note</span><span class="info-val">{note}</span></div>'
    if remarks: extra += f'<div class="info-row"><span class="info-label">Official Remarks</span><span class="info-val">{remarks}</span></div>'
    resolved_note = ''
    if new_status == 'resolved':
        resolved_note = '<div style="background:#E0F2E9;border-radius:10px;padding:14px;margin-top:14px"><strong>✅ Issue Resolved!</strong><br>Please log in to confirm the resolution or dispute it if the problem still persists.</div>'
    body = f"""
<p>Hi <strong>{user.name}</strong>,</p>
<p>The status of your complaint has been updated:</p>
<div style="background:#f4faf7;border-radius:10px;padding:16px;margin:12px 0">
  <div class="info-row"><span class="info-label">Complaint</span><span class="info-val">#{complaint.id} – {complaint.title}</span></div>
  <div class="info-row"><span class="info-label">Previous Status</span><span class="info-val">{old_label}</span></div>
  <div class="info-row"><span class="info-label">New Status</span><span class="info-val"><span class="status-badge" style="background:{accent}">{new_label}</span></span></div>
  {extra}
</div>{resolved_note}"""
    _send(user.email,
          f'[CivicAlert] Complaint #{complaint.id} → {new_label}',
          _html(body, f'Status Update: #{complaint.id}', accent=accent))


def send_resolution_proof_uploaded(complaint):
    user = complaint.reporter
    if not user: return
    body = f"""
<p>Hi <strong>{user.name}</strong>,</p>
<p>An official has uploaded a <strong>resolution proof photo</strong> for your complaint:</p>
<div style="background:#f4faf7;border-radius:10px;padding:16px;margin:12px 0">
  <div class="info-row" style="border:none"><span class="info-label">Complaint</span><span class="info-val">#{complaint.id} – {complaint.title}</span></div>
</div>
<p>Please log in and <strong>confirm</strong> whether the issue has been fixed, or <strong>dispute</strong> it if it hasn't.</p>"""
    _send(user.email,
          f'[CivicAlert] Resolution Proof for #{complaint.id} – Action Required',
          _html(body, 'Resolution Proof Uploaded'))


def send_otp_email(user, otp: str):
    body = f"""
<p>Hi <strong>{user.name}</strong>,</p>
<p>Use the code below to verify your phone number. This code expires in <strong>10 minutes</strong>.</p>
<div class="otp-box">
  <div style="font-size:.85rem;color:#5B7B7A;margin-bottom:8px;font-weight:600">YOUR VERIFICATION CODE</div>
  <div class="otp-code">{otp}</div>
</div>
<p style="color:#6b7280;font-size:.85rem">Do not share this code with anyone. CivicAlert staff will never ask for it.</p>"""
    _send(user.email,
          '[CivicAlert] Your OTP Verification Code',
          _html(body, 'Phone Verification'))
