from flask import Flask, render_template


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/wireframe")
    def wireframe():
        return render_template("wireframe.html")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

from flask import Flask, render_template, redirect, url_for
import os
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_required
from models import db, User, ValuationRequest

# Blueprints
from routes.auth_routes import auth
from routes.admin_routes import admin_bp
from routes.company_routes import company_bp
from routes.bank_routes import bank_bp
from routes.client_routes import client_bp
from routes.main_routes import main
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    # Ensure upload folder exists
    os.makedirs(app.config.get('UPLOAD_FOLDER', ''), exist_ok=True)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # تسجيل Blueprints
    app.register_blueprint(auth)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(company_bp, url_prefix='/company')
    app.register_blueprint(bank_bp, url_prefix='/bank')
    app.register_blueprint(client_bp, url_prefix='/client')
    app.register_blueprint(main)

    # الصفحة الرئيسية
    @app.route('/')
    def index():
        return render_template('landing.html')

    @app.route('/companies')
    def companies_public():
        companies = User.query.filter_by(role='company').all()
        return render_template('companies.html', companies=companies)

    # إعادة توجيه حسب الدور بعد تسجيل الدخول
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

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
        # إنشاء حساب المدير الافتراضي إذا لم يوجد
        if User.query.filter_by(role='admin').count() == 0:
            admin_user = User(name="مدير النظام", email="admin@platform.com", role="admin")
            admin_user.set_password("123")
            db.session.add(admin_user)
            db.session.commit()

    app.run(host='0.0.0.0', port=5000, debug=True)
