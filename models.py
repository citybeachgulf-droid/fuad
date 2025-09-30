"""SQLAlchemy models and helper to seed sample data."""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(255), nullable=False)  # NOTE: store hashed password in production
    role = db.Column(db.String(50), nullable=False)  # client, admin, company, bank
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.email}>'

class ValuationRequest(db.Model):
    __tablename__ = 'valuation_requests'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    bank_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    value = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(50), default='pending')  # pending/approved/completed/revision_requested
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship('User', foreign_keys=[client_id], backref='requests_made')
    company = db.relationship('User', foreign_keys=[company_id], backref='requests_assigned')
    bank = db.relationship('User', foreign_keys=[bank_id], backref='requests_for_bank')

    def __repr__(self):
        return f'<ValuationRequest {self.id} - {self.title}>'

def create_sample_data():
    """Create sample users and valuation requests for demo dashboards."""
    if User.query.count() > 0:
        return
    u_admin = User(email='admin@example.com', name='Admin User', password='admin', role='admin')
    u_company = User(email='company@example.com', name='Valuation Co', password='company', role='company')
    u_bank = User(email='bank@example.com', name='Bank User', password='bank', role='bank')
    u_client = User(email='client@example.com', name='Client User', password='client', role='client')
    db.session.add_all([u_admin, u_company, u_bank, u_client])
    db.session.commit()

    vr1 = ValuationRequest(title='Apartment 101', description='3BR apartment near sea', client_id=u_client.id, company_id=u_company.id, bank_id=u_bank.id, value=None, status='pending')
    vr2 = ValuationRequest(title='Plot A', description='Residential plot', client_id=u_client.id, company_id=u_company.id, bank_id=u_bank.id, value=120000.0, status='completed')
    db.session.add_all([vr1, vr2])
    db.session.commit()
    print('Sample data created.')
