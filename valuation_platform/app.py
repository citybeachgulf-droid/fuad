"""Main entry point for Valuation Platform.
Run: python app.py
This will start the Flask development server and register blueprints for the four portals.
"""
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_required

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
    login_manager.login_view = 'client.login'  # default login view
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # register blueprints
    app.register_blueprint(client_bp, url_prefix='/client')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(company_bp, url_prefix='/company')
    app.register_blueprint(bank_bp, url_prefix='/bank')

    # simple index route
    @app.route('/')
    def index():
        return render_template('index.html')

    # dashboard route redirect example
    @app.route('/dashboard')
    @login_required
    def dashboard():
        # basic dispatcher: redirect by role to correct portal
        role = getattr(current_user, 'role', None)
        if role == 'admin':
            return render_template('admin/dashboard.html')
        elif role == 'company':
            return render_template('company/dashboard.html')
        elif role == 'bank':
            return render_template('bank/dashboard.html')
        else:
            return render_template('client/dashboard.html')

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # create database and sample data if not exists
        db.create_all()
        # create sample data if empty
        if User.query.count() == 0:
            from models import create_sample_data
            create_sample_data()
    app.run(host='0.0.0.0', port=5000, debug=True)
