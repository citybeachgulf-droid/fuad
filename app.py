"""
Main entry point for Valuation Platform.
Run: python app.py
This will start the Flask development server and register blueprints for the four portals.
"""
from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_required
from routes.auth_routes import auth
from config import Config
from models import db, User, ValuationRequest

# Blueprints
from routes.client_routes import client_bp
from routes.admin_routes import admin_bp
from routes.company_routes import company_bp
from routes.bank_routes import bank_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'  # default login view for protected routes
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # register blueprints
    app.register_blueprint(client_bp, url_prefix='/client')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(company_bp, url_prefix='/company')
    app.register_blueprint(bank_bp, url_prefix='/bank')
    app.register_blueprint(auth)

    # --- Main Landing Page (Open to all clients) ---
    @app.route('/')
    def index():
        # صفحة رئيسية مفتوحة للعميل
        # تحتوي على Hero Section، عرض نسب الفائدة، وزر تسجيل الدخول للمدير/البنوك/الشركات
        return render_template('landing.html')

    # --- Dashboard route (protected) ---
    @app.route('/dashboard')
    @login_required
    def dashboard():
        # إعادة توجيه المستخدم حسب دوره بعد تسجيل الدخول
        role = getattr(current_user, 'role', None)
        if role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif role == 'company':
            return redirect(url_for('company.dashboard'))
        elif role == 'bank':
            return redirect(url_for('bank.dashboard'))
        else:
            return redirect(url_for('client.dashboard'))

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # إنشاء قاعدة البيانات والجداول
        db.create_all()

        # إنشاء حساب المدير الافتراضي إذا لم يكن موجود
        if User.query.filter_by(role='admin').count() == 0:
          admin_user = User(
        name='مدير النظام',
        email='admin@platform.com',
        role='admin'
    )
        admin_user.set_password('123')  # تعيين كلمة المرور المشفرة
        db.session.add(admin_user)
        db.session.commit()


        # إنشاء بيانات تجريبية إذا كانت قاعدة البيانات فارغة
        if User.query.count() == 1:  # فقط بعد إضافة المدير
            from models import create_sample_data
            create_sample_data()

    # تشغيل السيرفر على جميع الشبكات المحلية، بورت 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
