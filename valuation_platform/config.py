"""Configuration for Flask app. Uses SQLite by default. Edit as needed."""
import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-123')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(basedir, "valuation.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
