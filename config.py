"""Configuration for Flask app. Uses SQLite by default. Edit as needed."""
import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-123')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(basedir, "valuation.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Timezone used to interpret naive datetime inputs from admin forms
    TIMEZONE = os.environ.get('TIMEZONE', 'Asia/Muscat')
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
    # Optional: explicitly set the public base URL used to build callbacks, e.g. "https://app.example.com"
    EXTERNAL_BASE_URL = os.environ.get('EXTERNAL_BASE_URL')

    # OAuth configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    # Third-party sign-in config removed

    # SMS provider (Twilio) for OTP
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_FROM_NUMBER = os.environ.get('TWILIO_FROM_NUMBER')
    OTP_TTL_SECONDS = int(os.environ.get('OTP_TTL_SECONDS', '300'))
