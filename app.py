from flask import Flask
from extensions import db, login_manager, mail, limiter, migrate
import os


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')

    # ── Database ──────────────────────────────────────────────────────────────
    # Locally:     uses SQLite (instance/civic.db) — zero setup needed
    # Production:  set DATABASE_URL env var to your Postgres/Neon connection string
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',
        'sqlite:///civic.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ── Uploads ───────────────────────────────────────────────────────────────
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # ── Email ─────────────────────────────────────────────────────────────────
    # Set MAIL_USERNAME and MAIL_PASSWORD env vars for real emails.
    # If not set, OTPs print to terminal — fine for local dev.
    app.config['MAIL_SERVER']         = 'smtp.zoho.in'
    app.config['MAIL_PORT']           = 587
    app.config['MAIL_USE_TLS']        = True
    app.config['MAIL_USERNAME']       = os.environ.get('MAIL_USERNAME', '')
    app.config['MAIL_PASSWORD']       = os.environ.get('MAIL_PASSWORD', '')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', '')

    # ── Init extensions ───────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'

    # ── Blueprints ────────────────────────────────────────────────────────────
    from routes.auth import auth_bp
    from routes.complaints import complaints_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
# ── Create tables with retry (handles slow DNS on startup) ───────────────
    import time
    with app.app_context():
        for attempt in range(10):
            try:
                db.create_all()
                _seed_admin()
                break
            except Exception as e:
                if attempt < 9:
                    print(f"⏳ Database not ready yet, retrying in 3s... ({attempt+1}/10)")
                    time.sleep(3)
                else:
                    print(f"❌ Could not connect to database after 10 attempts: {e}")
                    raise
    return app


def _seed_admin():
    from models.user import User
    if not User.query.filter_by(role='admin').first():
        admin = User(
            name='Admin',
            email='admin@civic.gov.in',
            role='admin',
            ward='N/A',
            email_verified=True,
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin account created — email: admin@civic.gov.in  password: admin123")


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
