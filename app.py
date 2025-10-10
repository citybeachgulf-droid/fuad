from flask import Flask, render_template, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
import os
from flask_login import LoginManager, current_user, login_required
from models import db, User, ValuationRequest, BankProfile, BankOffer
from sqlalchemy import inspect, text
from authlib.integrations.flask_client import OAuth  # ✅ ضروري
from config import Config

# Blueprints
from routes.auth_routes import auth
from routes.admin_routes import admin_bp
from routes.company_routes import company_bp
from routes.bank_routes import bank_bp
from routes.client_routes import client_bp
from routes.main_routes import main
from routes.conversation_routes import conversations_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    # Respect proxy headers (X-Forwarded-Proto/Host) to generate correct external URLs
    # Trust a single proxy by default; adjust if your deployment has more hops.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    db.init_app(app)

    # إعداد OAuth
    oauth = OAuth(app)
    google = oauth.register(
        name='google',
        client_id='35722269243-fdj189u3r1n05rnsmp6q2vjcdhs4vcui.apps.googleusercontent.com',
        client_secret='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',
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

    # Ensure upload folders exist
    os.makedirs(app.config.get('UPLOAD_FOLDER', ''), exist_ok=True)
    os.makedirs(app.config.get('NEWS_UPLOAD_FOLDER', ''), exist_ok=True)
    os.makedirs(app.config.get('ADS_UPLOAD_FOLDER', ''), exist_ok=True)

    # إعداد LoginManager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    app.register_blueprint(auth)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(company_bp, url_prefix='/company')
    app.register_blueprint(bank_bp, url_prefix='/bank')
    app.register_blueprint(client_bp, url_prefix='/client')
    app.register_blueprint(main)
    app.register_blueprint(conversations_bp)

    @app.route('/health')
    def health():
        return {"status": "ok"}

    @app.route('/dashboard')
    @login_required
    def dashboard():
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'company':
            return redirect(url_for('company.dashboard'))
        elif current_user.role == 'bank':
            return redirect(url_for('bank.dashboard'))
        else:
            return redirect(url_for('main.landing'))

    # ✅ نرجع الكائنات المهمة لاستخدامها في باقي الملفات
    app.oauth = oauth
    app.google = google

    return app


app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # تحديث الجداول تلقائياً إذا لزم
        try:
            inspector = inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('company_approved_banks')]
            if 'limit_value' not in cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE company_approved_banks ADD COLUMN limit_value FLOAT'))

            user_cols = [c['name'] for c in inspector.get_columns('users')]
            with db.engine.connect() as conn:
                if 'oauth_provider' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN oauth_provider VARCHAR(50)"))
                if 'oauth_subject' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN oauth_subject VARCHAR(255)"))
                if 'email_verified' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0 NOT NULL"))

            # Ensure advertisements.stored_in_utc exists
            ads_cols = [c['name'] for c in inspector.get_columns('advertisements')]
            if 'stored_in_utc' not in ads_cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE advertisements ADD COLUMN stored_in_utc BOOLEAN DEFAULT 0 NOT NULL'))
        except Exception:
            pass

        # إنشاء مدير النظام إذا لم يوجد
        if User.query.filter_by(role='admin').count() == 0:
            admin_user = User(name="مدير النظام", email="admin@platform.com", role="admin")
            admin_user.set_password("123")
            db.session.add(admin_user)
            db.session.commit()

        # بيانات البنوك العمانية
        def seed_omani_banks():
            banks = [
                {"name": "Bank Muscat", "slug": "bank-muscat", "website": "https://www.bankmuscat.com/"},
                {"name": "Bank Dhofar", "slug": "bank-dhofar", "website": "https://www.bankdhofar.com/"},
                {"name": "Sohar International", "slug": "sohar-international", "website": "https://soharinternational.com/"},
                {"name": "National Bank of Oman", "slug": "nbo", "website": "https://www.nbo.om/"},
                {"name": "Oman Arab Bank", "slug": "oman-arab-bank", "website": "https://www.oman-arabbank.com/"},
                {"name": "Ahli Bank", "slug": "ahli-bank", "website": "https://ahlibank.om/"},
                {"name": "HSBC Oman", "slug": "hsbc-oman", "website": "https://www.hsbc.co.om/"},
                {"name": "Bank Nizwa", "slug": "bank-nizwa", "website": "https://www.banknizwa.om/"},
                {"name": "Alizz Islamic Bank", "slug": "alizz-islamic-bank", "website": "https://alizzib.com/"},
            ]

            if BankProfile.query.count() > 0:
                return

            for b in banks:
                email = f"{b['slug']}@banks.om"
                existing_user = User.query.filter_by(email=email).first()
                if not existing_user:
                    u = User(name=b["name"], email=email, role="bank")
                    u.set_password("123")
                    db.session.add(u)
                    db.session.flush()
                else:
                    u = existing_user

                profile = BankProfile(
                    user_id=u.id,
                    slug=b["slug"],
                    website=b.get("website"),
                    about=f"عروض تمويل من {b['name']}"
                )
                db.session.add(profile)
                db.session.flush()

                offer = BankOffer(
                    bank_profile_id=profile.id,
                    product_name="قرض سكني",
                    rate_type="ثابت",
                    interest_rate=5.75,
                    min_amount=10000,
                    max_amount=300000,
                    min_tenure_months=12,
                    max_tenure_months=300,
                    notes="عرض توضيحي"
                )
                db.session.add(offer)

            db.session.commit()

        seed_omani_banks()

    # ✅ تشغيل التطبيق
    app.run(host='0.0.0.0', port=5000, debug=True)
