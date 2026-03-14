import re
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, limiter
from models.user import User
from services.email import send_otp_email

auth_bp = Blueprint('auth', __name__)

PHONE_RE = re.compile(r'^[6-9][0-9]{9}$')


def clean_phone(raw):
    p = raw.strip().replace(' ', '').replace('-', '')
    if p.startswith('+91'):               p = p[3:]
    elif p.startswith('91') and len(p) == 12: p = p[2:]
    return p


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('complaints.dashboard'))

    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        phone    = clean_phone(request.form.get('phone', ''))
        ward     = request.form.get('ward', '').strip()

        errors = []
        if not name:            errors.append('Name is required.')
        if not email:           errors.append('Email is required.')
        if len(password) < 6:  errors.append('Password must be at least 6 characters.')
        if password != confirm: errors.append('Passwords do not match.')
        if phone and not PHONE_RE.match(phone):
            errors.append('Mobile number must be exactly 10 digits and start with 6–9.')
        if User.query.filter_by(email=email).first():
            errors.append('An account with this email already exists.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('auth/register.html',
                                   name=name, email=email, phone=phone, ward=ward)

        user = User(name=name, email=email, phone=phone or None,
                    ward=ward, role='citizen', email_verified=False)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Send OTP via email
        otp = user.generate_otp()
        db.session.commit()
        send_otp_email(user, otp)
        session['verify_user_id'] = user.id
        flash('Account created! Check your email for the OTP to verify your account.', 'info')
        return redirect(url_for('auth.verify_otp'))

    return render_template('auth/register.html')


@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
@limiter.limit("10 per minute; 30 per hour")
def verify_otp():
    user_id = session.get('verify_user_id')
    if not user_id:
        return redirect(url_for('auth.register'))
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        code = request.form.get('otp', '').strip()
        if user.verify_otp(code):
            db.session.commit()
            session.pop('verify_user_id', None)
            flash('Email verified! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid or expired OTP. Try again or resend.', 'danger')

    return render_template('auth/verify_otp.html', email=user.email)


@auth_bp.route('/verify-otp/resend', methods=['POST'])
@limiter.limit("3 per 10 minutes")
def resend_otp():
    user_id = session.get('verify_user_id')
    if not user_id:
        return redirect(url_for('auth.register'))
    user = User.query.get(user_id)
    if user:
        otp = user.generate_otp()
        db.session.commit()
        send_otp_email(user, otp)
        flash('A new OTP has been sent to your email.', 'info')
    return redirect(url_for('auth.verify_otp'))


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute; 50 per hour")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('complaints.dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.email_verified:
                session['verify_user_id'] = user.id
                flash('Please verify your email before logging in. Enter the OTP sent to your email.', 'warning')
                return redirect(url_for('auth.verify_otp'))
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.name}!', 'success')
            if user.role in ('admin', 'official'):
                return redirect(next_page or url_for('admin.dashboard'))
            return redirect(next_page or url_for('complaints.dashboard'))
        flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
