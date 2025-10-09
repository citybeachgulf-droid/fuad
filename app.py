from flask import Flask, render_template, redirect, url_for
import os
from flask_login import LoginManager, current_user, login_required
from models import db, User, ValuationRequest, BankProfile, BankOffer
from sqlalchemy import inspect, text

# Blueprints
from routes.auth_routes import auth
from routes.admin_routes import admin_bp
from routes.company_routes import company_bp
from routes.bank_routes import bank_bp
from routes.client_routes import client_bp
from routes.main_routes import main
from config import Config


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    # Ensure upload folders exist
    os.makedirs(app.config.get('UPLOAD_FOLDER', ''), exist_ok=True)
    os.makedirs(app.config.get('NEWS_UPLOAD_FOLDER', ''), exist_ok=True)
    os.makedirs(app.config.get('ADS_UPLOAD_FOLDER', ''), exist_ok=True)

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

    @app.route('/health')
    def health():
        return {"status": "ok"}

    # Redirect to role dashboards after login
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
            return redirect(url_for('client.dashboard'))

    return app


app = create_app()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Lightweight migration: ensure new columns and fields exist
        try:
            inspector = inspect(db.engine)
            # company_approved_banks.limit_value
            cols = [c['name'] for c in inspector.get_columns('company_approved_banks')]
            if 'limit_value' not in cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE company_approved_banks ADD COLUMN limit_value FLOAT'))

            # users.oauth_provider, users.oauth_subject, users.email_verified
            user_cols = [c['name'] for c in inspector.get_columns('users')]
            with db.engine.connect() as conn:
                if 'oauth_provider' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN oauth_provider VARCHAR(50)"))
                if 'oauth_subject' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN oauth_subject VARCHAR(255)"))
                if 'email_verified' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0 NOT NULL"))
        except Exception:
            # Fail silently to avoid startup crash; model will still work for new DBs
            pass
        # إنشاء حساب المدير الافتراضي إذا لم يوجد
        if User.query.filter_by(role='admin').count() == 0:
            admin_user = User(name="مدير النظام", email="admin@platform.com", role="admin")
            admin_user.set_password("123")
            db.session.add(admin_user)
            db.session.commit()

        # Seed major Omani banks and sample offers
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
                # Create user for bank
                email = f"{b['slug']}@banks.om"
                existing_user = User.query.filter_by(email=email).first()
                if not existing_user:
                    u = User(name=b["name"], email=email, role="bank")
                    u.set_password("123")
                    db.session.add(u)
                    db.session.flush()
                else:
                    u = existing_user

                profile = BankProfile(user_id=u.id, slug=b["slug"], website=b.get("website"), about=f"عروض تمويل من {b['name']}")
                db.session.add(profile)
                db.session.flush()

                # Sample offers (illustrative only)
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

    app.run(host='0.0.0.0', port=5000, debug=True)
