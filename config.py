"""Configuration for Flask app. Uses SQLite by default. Edit as needed."""
import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-123')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(basedir, "valuation.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(basedir, 'static', 'uploads', 'logos'))
    NEWS_UPLOAD_FOLDER = os.environ.get('NEWS_UPLOAD_FOLDER', os.path.join(basedir, 'static', 'uploads', 'news'))
    ADS_UPLOAD_FOLDER = os.environ.get('ADS_UPLOAD_FOLDER', os.path.join(basedir, 'static', 'uploads', 'ads'))
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024))
    # Mail settings (SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'no-reply@localhost')
    # Optional: used for external URL generation; set to your domain (e.g., example.com)
    SERVER_NAME = os.environ.get('SERVER_NAME')

    # OAuth configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

    # Apple Sign In (set APPLE_CLIENT_SECRET to a pre-generated JWT)
    APPLE_CLIENT_ID = os.environ.get('APPLE_CLIENT_ID')
    APPLE_CLIENT_SECRET = os.environ.get('APPLE_CLIENT_SECRET')
