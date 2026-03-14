import os
import uuid
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app, abort, jsonify)
from flask_login import login_required, current_user
from extensions import db
from models.complaint import Complaint, StatusHistory, UpvoteLog
from services.email import send_complaint_submitted

complaints_bp = Blueprint('complaints', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
CATEGORIES = [
    'Pothole / Road Damage',
    'Garbage / Waste',
    'Street Light',
    'Water Supply',
    'Sewage / Drainage',
    'Encroachment',
    'Stray Animals',
    'Tree / Branch',
    'Noise Pollution',
    'Other',
]
PRIORITIES = ['low', 'medium', 'high', 'urgent']


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_image(file):
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name))
    return unique_name


def find_duplicates(category, ward, exclude_id=None):
    """
    Return recent open complaints with the same category + ward (last 7 days).
    Used for duplicate detection before submission.
    """
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=7)
    query = (Complaint.query
             .filter_by(category=category)
             .filter(Complaint.status.notin_(['resolved', 'rejected']))
             .filter(Complaint.created_at >= cutoff))
    if ward:
        query = query.filter(Complaint.ward.ilike(f'%{ward}%'))
    if exclude_id:
        query = query.filter(Complaint.id != exclude_id)
    return query.order_by(Complaint.upvotes.desc()).limit(5).all()


# ── Landing ───────────────────────────────────────────────────────────────────

@complaints_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('complaints.dashboard'))
    return render_template('index.html')


# ── Citizen dashboard ─────────────────────────────────────────────────────────

@complaints_bp.route('/dashboard')
@login_required
def dashboard():
    my_complaints = (Complaint.query
                     .filter_by(user_id=current_user.id)
                     .order_by(Complaint.created_at.desc())
                     .all())
    stats = {
        'total':       len(my_complaints),
        'pending':     sum(1 for c in my_complaints if c.status == 'pending'),
        'in_progress': sum(1 for c in my_complaints if c.status == 'in_progress'),
        'resolved':    sum(1 for c in my_complaints if c.status == 'resolved'),
    }
    return render_template('complaints/dashboard.html',
                           complaints=my_complaints, stats=stats)


# ── AJAX: duplicate check ─────────────────────────────────────────────────────

@complaints_bp.route('/check-duplicates')
@login_required
def check_duplicates():
    """Called via fetch() on the submit form when category/ward changes."""
    category = request.args.get('category', '')
    ward     = request.args.get('ward', current_user.ward or '')
    if not category:
        return jsonify([])
    dupes = find_duplicates(category, ward)
    return jsonify([{
        'id':       c.id,
        'title':    c.title,
        'address':  c.address,
        'status':   c.status,
        'upvotes':  c.upvotes,
        'created':  c.created_at.strftime('%d %b %Y'),
    } for c in dupes])


# ── Submit ────────────────────────────────────────────────────────────────────

@complaints_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category    = request.form.get('category', '').strip()
        priority    = request.form.get('priority', 'medium')
        address     = request.form.get('address', '').strip()
        ward        = request.form.get('ward', '').strip()
        latitude    = request.form.get('latitude') or None
        longitude   = request.form.get('longitude') or None
        force_submit= request.form.get('force_submit') == '1'

        errors = []
        if not title:               errors.append('Title is required.')
        if not description:         errors.append('Description is required.')
        if category not in CATEGORIES: errors.append('Please select a valid category.')
        if not address:             errors.append('Address is required.')

        image_filename = None
        file = request.files.get('image')
        if file and file.filename:
            if not allowed_file(file.filename):
                errors.append('Only image files (JPG, PNG, WEBP, GIF) are allowed.')
            else:
                image_filename = save_uploaded_image(file)

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('complaints/submit.html',
                                   categories=CATEGORIES, priorities=PRIORITIES,
                                   form=request.form)

        # ── Duplicate check ───────────────────────────────────────
        if not force_submit:
            dupes = find_duplicates(category, ward or current_user.ward or '')
            if dupes:
                return render_template('complaints/submit.html',
                                       categories=CATEGORIES, priorities=PRIORITIES,
                                       form=request.form,
                                       duplicates=dupes,
                                       show_duplicate_warning=True)

        # ── Save complaint ────────────────────────────────────────
        complaint = Complaint(
            title=title, description=description,
            category=category, priority=priority,
            address=address, ward=ward or current_user.ward,
            latitude=float(latitude) if latitude else None,
            longitude=float(longitude) if longitude else None,
            image_filename=image_filename,
            user_id=current_user.id, status='pending',
        )
        db.session.add(complaint)
        db.session.flush()

        db.session.add(StatusHistory(
            complaint_id=complaint.id, old_status=None, new_status='pending',
            changed_by=current_user.id, note='Complaint submitted by citizen.',
        ))
        db.session.commit()

        # ── Email notification ────────────────────────────────────
        send_complaint_submitted(complaint)

        flash(f'Complaint #{complaint.id} submitted successfully!', 'success')
        return redirect(url_for('complaints.detail', complaint_id=complaint.id))

    return render_template('complaints/submit.html',
                           categories=CATEGORIES, priorities=PRIORITIES, form={})


# ── Detail ────────────────────────────────────────────────────────────────────

@complaints_bp.route('/complaint/<int:complaint_id>')
@login_required
def detail(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    if current_user.role == 'citizen' and complaint.user_id != current_user.id:
        abort(403)
    return render_template('complaints/detail.html', complaint=complaint)


# ── Upvote ────────────────────────────────────────────────────────────────────

@complaints_bp.route('/complaint/<int:complaint_id>/upvote', methods=['POST'])
@login_required
def upvote(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    if complaint.user_id == current_user.id:
        flash("You can't upvote your own complaint.", 'warning')
    else:
        already_voted = UpvoteLog.query.filter_by(
            complaint_id=complaint_id, user_id=current_user.id
        ).first()
        if already_voted:
            flash("You've already upvoted this complaint.", 'warning')
        else:
            complaint.upvotes += 1
            db.session.add(UpvoteLog(complaint_id=complaint_id, user_id=current_user.id))
            db.session.commit()
            flash('Upvoted!', 'success')
    return redirect(url_for('complaints.detail', complaint_id=complaint_id))

# ── Confirm / Dispute resolution (citizen) ────────────────────────────────────

@complaints_bp.route('/complaint/<int:complaint_id>/confirm-resolution', methods=['POST'])
@login_required
def confirm_resolution(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    if complaint.user_id != current_user.id:
        abort(403)
    if complaint.status != 'resolved':
        flash('Complaint is not marked as resolved yet.', 'warning')
        return redirect(url_for('complaints.detail', complaint_id=complaint_id))

    action = request.form.get('action')  # 'confirm' or 'dispute'
    reason = request.form.get('reason', '').strip()

    if action == 'confirm':
        complaint.resolution_confirmed = True
        db.session.add(StatusHistory(
            complaint_id=complaint.id, old_status='resolved', new_status='resolved',
            changed_by=current_user.id, note='Citizen confirmed resolution.',
        ))
        flash('Thank you for confirming the resolution!', 'success')
    elif action == 'dispute':
        complaint.resolution_confirmed = False
        complaint.resolution_dispute_reason = reason
        complaint.status = 'disputed'
        db.session.add(StatusHistory(
            complaint_id=complaint.id, old_status='resolved', new_status='disputed',
            changed_by=current_user.id,
            note=f'Citizen disputed resolution: {reason}',
        ))
        flash('Resolution disputed. Officials have been notified.', 'warning')

    db.session.commit()
    return redirect(url_for('complaints.detail', complaint_id=complaint_id))


# ── Community feed ────────────────────────────────────────────────────────────

@complaints_bp.route('/feed')
@login_required
def feed():
    ward_filter     = request.args.get('ward', current_user.ward or '')
    category_filter = request.args.get('category', '')
    status_filter   = request.args.get('status', '')
    page            = request.args.get('page', 1, type=int)

    query = Complaint.query
    if ward_filter:     query = query.filter(Complaint.ward.ilike(f'%{ward_filter}%'))
    if category_filter: query = query.filter_by(category=category_filter)
    if status_filter:   query = query.filter_by(status=status_filter)

    complaints = query.order_by(Complaint.created_at.desc()).paginate(page=page, per_page=20, error_out=False)

    return render_template('complaints/feed.html',
                           complaints=complaints, categories=CATEGORIES,
                           ward_filter=ward_filter, category_filter=category_filter,
                           status_filter=status_filter)


# ── Edit complaint (citizen, only if pending/acknowledged) ────────────────────

@complaints_bp.route('/complaint/<int:complaint_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)

    if complaint.user_id != current_user.id:
        abort(403)
    if complaint.status not in ('pending', 'acknowledged'):
        flash('Complaints can only be edited while pending or acknowledged.', 'warning')
        return redirect(url_for('complaints.detail', complaint_id=complaint_id))

    if request.method == 'POST':
        complaint.title       = request.form.get('title', '').strip() or complaint.title
        complaint.description = request.form.get('description', '').strip() or complaint.description
        complaint.category    = request.form.get('category', complaint.category)
        complaint.priority    = request.form.get('priority', complaint.priority)
        complaint.address     = request.form.get('address', '').strip() or complaint.address
        complaint.ward        = request.form.get('ward', '').strip() or complaint.ward
        lat = request.form.get('latitude')
        lng = request.form.get('longitude')
        if lat: complaint.latitude  = float(lat)
        if lng: complaint.longitude = float(lng)

        # Replace image if new one uploaded
        file = request.files.get('image')
        if file and file.filename:
            if allowed_file(file.filename):
                complaint.image_filename = save_uploaded_image(file)
            else:
                flash('Invalid image format. Image not updated.', 'warning')

        db.session.add(StatusHistory(
            complaint_id=complaint.id,
            old_status=complaint.status,
            new_status=complaint.status,
            changed_by=current_user.id,
            note='Complaint details edited by citizen.',
        ))
        db.session.commit()
        flash('Complaint updated successfully.', 'success')
        return redirect(url_for('complaints.detail', complaint_id=complaint_id))

    return render_template('complaints/edit.html',
                           complaint=complaint,
                           categories=CATEGORIES,
                           priorities=PRIORITIES)
