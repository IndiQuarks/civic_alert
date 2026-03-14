import os
import uuid
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort, jsonify, current_app)
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from extensions import db
from models.complaint import Complaint, StatusHistory
from models.user import User
from services.email import send_status_changed, send_resolution_proof_uploaded

admin_bp = Blueprint('admin', __name__)

VALID_STATUSES = ['pending', 'acknowledged', 'in_progress', 'resolved', 'rejected']
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def admin_or_official_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role not in ('admin', 'official'):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def _save_image(file):
    ext = file.filename.rsplit('.', 1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], name))
    return name


# ── Admin dashboard ───────────────────────────────────────────────────────────

@admin_bp.route('/')
@login_required
@admin_or_official_required
def dashboard():
    total        = Complaint.query.count()
    pending      = Complaint.query.filter_by(status='pending').count()
    in_progress  = Complaint.query.filter_by(status='in_progress').count()
    resolved     = Complaint.query.filter_by(status='resolved').count()
    rejected     = Complaint.query.filter_by(status='rejected').count()
    acknowledged = Complaint.query.filter_by(status='acknowledged').count()
    disputed     = Complaint.query.filter_by(status='disputed').count()

    recent = Complaint.query.order_by(Complaint.created_at.desc()).limit(10).all()
    urgent = (Complaint.query
              .filter(Complaint.priority == 'urgent',
                      Complaint.status.notin_(['resolved', 'rejected']))
              .order_by(Complaint.created_at.asc()).all())

    stats = dict(total=total, pending=pending, in_progress=in_progress,
                 resolved=resolved, rejected=rejected,
                 acknowledged=acknowledged, disputed=disputed)

    return render_template('admin/dashboard.html',
                           stats=stats, recent=recent, urgent=urgent)


# ── Complaints list ───────────────────────────────────────────────────────────

@admin_bp.route('/complaints')
@login_required
@admin_or_official_required
def complaints_list():
    status   = request.args.get('status', '')
    category = request.args.get('category', '')
    priority = request.args.get('priority', '')
    ward     = request.args.get('ward', '')
    search   = request.args.get('search', '').strip()
    page     = request.args.get('page', 1, type=int)

    query = Complaint.query
    if status:   query = query.filter_by(status=status)
    if category: query = query.filter_by(category=category)
    if priority: query = query.filter_by(priority=priority)
    if ward:     query = query.filter(Complaint.ward.ilike(f'%{ward}%'))
    if search:
        query = query.filter(
            Complaint.title.ilike(f'%{search}%') |
            Complaint.description.ilike(f'%{search}%') |
            Complaint.address.ilike(f'%{search}%')
        )

    complaints = query.order_by(Complaint.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    officials  = User.query.filter(User.role.in_(['admin', 'official'])).all()

    from routes.complaints import CATEGORIES
    return render_template('admin/complaints_list.html',
                           complaints=complaints, officials=officials,
                           categories=CATEGORIES, valid_statuses=VALID_STATUSES,
                           filters=dict(status=status, category=category,
                                        priority=priority, ward=ward, search=search))


# ── Complaint detail ──────────────────────────────────────────────────────────

@admin_bp.route('/complaints/<int:complaint_id>')
@login_required
@admin_or_official_required
def complaint_detail(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    officials = User.query.filter(User.role.in_(['admin', 'official'])).all()
    return render_template('admin/complaint_detail.html',
                           complaint=complaint, officials=officials,
                           valid_statuses=VALID_STATUSES)


# ── Update status (with email notification) ───────────────────────────────────

@admin_bp.route('/complaints/<int:complaint_id>/update-status', methods=['POST'])
@login_required
@admin_or_official_required
def update_status(complaint_id):
    complaint    = Complaint.query.get_or_404(complaint_id)
    new_status   = request.form.get('status', '').strip()
    note         = request.form.get('note', '').strip()
    admin_remarks= request.form.get('admin_remarks', '').strip()

    if new_status not in VALID_STATUSES:
        flash('Invalid status.', 'danger')
        return redirect(url_for('admin.complaint_detail', complaint_id=complaint_id))

    old_status = complaint.status
    complaint.status = new_status
    if admin_remarks:
        complaint.admin_remarks = admin_remarks
    if new_status == 'resolved':
        complaint.resolved_at = datetime.utcnow()

    db.session.add(StatusHistory(
        complaint_id=complaint.id, old_status=old_status, new_status=new_status,
        changed_by=current_user.id,
        note=note or f'Status updated by {current_user.name}',
    ))
    db.session.commit()

    # ── Email citizen ─────────────────────────────────────────────
    send_status_changed(complaint, old_status, new_status,
                        note=note, remarks=admin_remarks)

    flash(f'Status updated to "{new_status}".', 'success')
    return redirect(url_for('admin.complaint_detail', complaint_id=complaint_id))


# ── Upload resolution proof (Feature 4) ──────────────────────────────────────

@admin_bp.route('/complaints/<int:complaint_id>/upload-proof', methods=['POST'])
@login_required
@admin_or_official_required
def upload_resolution_proof(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    file = request.files.get('proof_image')

    if not file or not file.filename:
        flash('Please select an image file.', 'danger')
        return redirect(url_for('admin.complaint_detail', complaint_id=complaint_id))

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        flash('Only JPG/PNG/WEBP files allowed.', 'danger')
        return redirect(url_for('admin.complaint_detail', complaint_id=complaint_id))

    filename = _save_image(file)
    complaint.resolution_proof_filename = filename

    # Auto-set status to resolved if not already
    old_status = complaint.status
    if complaint.status not in ('resolved',):
        complaint.status = 'resolved'
        complaint.resolved_at = datetime.utcnow()
        db.session.add(StatusHistory(
            complaint_id=complaint.id, old_status=old_status, new_status='resolved',
            changed_by=current_user.id,
            note=f'Marked resolved with photo proof by {current_user.name}.',
        ))

    db.session.commit()

    # Notify citizen to confirm or dispute
    send_resolution_proof_uploaded(complaint)
    # Also send status-changed email
    if old_status != 'resolved':
        send_status_changed(complaint, old_status, 'resolved',
                            note='Resolution proof uploaded by official.')

    flash('Resolution proof uploaded. Citizen has been notified to confirm.', 'success')
    return redirect(url_for('admin.complaint_detail', complaint_id=complaint_id))


# ── Assign ────────────────────────────────────────────────────────────────────

@admin_bp.route('/complaints/<int:complaint_id>/assign', methods=['POST'])
@login_required
@admin_or_official_required
def assign(complaint_id):
    complaint   = Complaint.query.get_or_404(complaint_id)
    official_id = request.form.get('official_id', type=int)
    official    = User.query.get(official_id)

    if not official or official.role not in ('admin', 'official'):
        flash('Invalid official.', 'danger')
        return redirect(url_for('admin.complaint_detail', complaint_id=complaint_id))

    complaint.assigned_to = official.id
    if complaint.status == 'pending':
        old = complaint.status
        complaint.status = 'acknowledged'
        db.session.add(StatusHistory(
            complaint_id=complaint.id, old_status=old, new_status='acknowledged',
            changed_by=current_user.id, note=f'Assigned to {official.name}.',
        ))
        send_status_changed(complaint, old, 'acknowledged',
                            note=f'Assigned to {official.name}.')

    db.session.commit()
    flash(f'Assigned to {official.name}.', 'success')
    return redirect(url_for('admin.complaint_detail', complaint_id=complaint_id))


# ── Users ─────────────────────────────────────────────────────────────────────

@admin_bp.route('/users')
@login_required
def users_list():
    if current_user.role != 'admin':
        abort(403)
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users_list.html', users=users)


@admin_bp.route('/users/<int:user_id>/change-role', methods=['POST'])
@login_required
def change_role(user_id):
    if current_user.role != 'admin':
        abort(403)
    user     = User.query.get_or_404(user_id)
    new_role = request.form.get('role', '')
    if new_role not in ('citizen', 'official', 'admin'):
        flash('Invalid role.', 'danger')
        return redirect(url_for('admin.users_list'))
    user.role = new_role
    db.session.commit()
    flash(f'{user.name} is now a {new_role}.', 'success')
    return redirect(url_for('admin.users_list'))


# ── Analytics ─────────────────────────────────────────────────────────────────

@admin_bp.route('/analytics')
@login_required
@admin_or_official_required
def analytics():
    from sqlalchemy import func

    by_category = db.session.query(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category).all()
    by_status   = db.session.query(Complaint.status,   func.count(Complaint.id)).group_by(Complaint.status).all()
    by_ward     = (db.session.query(Complaint.ward, func.count(Complaint.id))
                   .filter(Complaint.ward != None)
                   .group_by(Complaint.ward)
                   .order_by(func.count(Complaint.id).desc())
                   .limit(10).all())

    resolved = Complaint.query.filter(Complaint.status == 'resolved', Complaint.resolved_at != None).all()
    avg_hours = 0
    if resolved:
        total_h = sum((c.resolved_at - c.created_at).total_seconds() / 3600 for c in resolved)
        avg_hours = round(total_h / len(resolved), 1)

    disputed_count   = Complaint.query.filter_by(status='disputed').count()
    confirmed_count  = Complaint.query.filter_by(resolution_confirmed=True).count()

    return render_template('admin/analytics.html',
                           by_category=by_category, by_status=by_status,
                           by_ward=by_ward, avg_hours=avg_hours,
                           resolved_count=len(resolved),
                           disputed_count=disputed_count,
                           confirmed_count=confirmed_count)


# ── JSON API ──────────────────────────────────────────────────────────────────

@admin_bp.route('/api/complaints')
@login_required
@admin_or_official_required
def api_complaints():
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).limit(200).all()
    return jsonify([{
        'id': c.id, 'title': c.title, 'category': c.category,
        'status': c.status, 'priority': c.priority, 'ward': c.ward,
        'address': c.address, 'latitude': c.latitude, 'longitude': c.longitude,
        'upvotes': c.upvotes, 'created_at': c.created_at.isoformat(),
        'reporter': c.reporter.name if c.reporter else None,
        'resolution_confirmed': c.resolution_confirmed,
    } for c in complaints])
