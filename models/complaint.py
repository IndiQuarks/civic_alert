from extensions import db
from datetime import datetime


class Complaint(db.Model):
    __tablename__ = 'complaints'

    # ── Core fields ──────────────────────────────────────────────
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category    = db.Column(db.String(50), nullable=False)
    priority    = db.Column(db.String(20), default='medium')  # low|medium|high|urgent

    # ── Location ─────────────────────────────────────────────────
    address   = db.Column(db.String(300), nullable=False)
    ward      = db.Column(db.String(100), nullable=True)
    latitude  = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # ── Status & assignment ───────────────────────────────────────
    status      = db.Column(db.String(30), default='pending')
    # pending → acknowledged → in_progress → resolved → rejected → disputed

    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assignee    = db.relationship('User', foreign_keys=[assigned_to])

    # ── Media ─────────────────────────────────────────────────────
    image_filename = db.Column(db.String(255), nullable=True)

    # ── Resolution proof (Feature 4) ──────────────────────────────
    resolution_proof_filename = db.Column(db.String(255), nullable=True)
    resolution_confirmed      = db.Column(db.Boolean, nullable=True)  # True=confirmed, False=disputed, None=pending
    resolution_dispute_reason = db.Column(db.Text, nullable=True)

    # ── Ownership & timestamps ────────────────────────────────────
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    # ── Admin notes ───────────────────────────────────────────────
    admin_remarks = db.Column(db.Text, nullable=True)

    # ── Upvotes ───────────────────────────────────────────────────
    upvotes = db.Column(db.Integer, default=0)

    # Relationships
    status_history = db.relationship('StatusHistory', backref='complaint',
                                     lazy=True, order_by='StatusHistory.changed_at')

    @property
    def status_badge_color(self):
        return {
            'pending':     'secondary',
            'acknowledged':'info',
            'in_progress': 'warning',
            'resolved':    'success',
            'rejected':    'danger',
            'disputed':    'danger',
        }.get(self.status, 'secondary')

    @property
    def priority_badge_color(self):
        return {
            'low':    'success',
            'medium': 'info',
            'high':   'warning',
            'urgent': 'danger',
        }.get(self.priority, 'secondary')

    def __repr__(self):
        return f'<Complaint #{self.id} [{self.status}] {self.title[:40]}>'


class UpvoteLog(db.Model):
    """Tracks which users have upvoted which complaints to prevent duplicates."""
    __tablename__ = 'upvote_log'

    id           = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('complaint_id', 'user_id', name='uq_upvote_per_user'),
    )


class StatusHistory(db.Model):
    __tablename__ = 'status_history'

    id           = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    old_status   = db.Column(db.String(30))
    new_status   = db.Column(db.String(30), nullable=False)
    changed_by   = db.Column(db.Integer, db.ForeignKey('users.id'))
    note         = db.Column(db.Text, nullable=True)
    changed_at   = db.Column(db.DateTime, default=datetime.utcnow)

    changer = db.relationship('User', foreign_keys=[changed_by])
