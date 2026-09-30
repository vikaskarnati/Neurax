"""
Configuration module.
Loads environment variables and stores central configuration settings such as database credentials, JWT secrets, and API keys.
"""
import os
import urllib.parse
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

def _build_db_url():
    """Build PostgreSQL connection URL from DATABASE_URL/POSTGRES_URL or DB_*/PG* environment variables."""
    db_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL') or os.getenv('POSTGRESQL_URL')
    if db_url:
        # Standardize postgres:// to postgresql:// for compatibility
        if db_url.startswith('postgres://'):
            db_url = 'postgresql://' + db_url[len('postgres://'):]
        return db_url

    host = os.getenv('DB_HOST') or os.getenv('PGHOST') or 'localhost'
    port = os.getenv('DB_PORT') or os.getenv('PGPORT') or '5432'
    user = os.getenv('DB_USER') or os.getenv('PGUSER') or 'postgres'
    password = os.getenv('DB_PASSWORD') or os.getenv('PGPASSWORD') or ''
    database = os.getenv('DB_NAME') or os.getenv('PGDATABASE') or 'neurax_db'

    encoded_user = urllib.parse.quote_plus(user)
    encoded_pass = urllib.parse.quote_plus(password)
    return f"postgresql://{encoded_user}:{encoded_pass}@{host}:{port}/{database}"

class Config:
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'neurax-jwt-secret')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY') or os.getenv('GROQ_API_KEY')
    GOOGLE_PLACES_KEY = os.getenv('GOOGLE_PLACES_KEY', '')
    MAIL_EMAIL = os.getenv('MAIL_EMAIL')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@neurax.com')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    DATABASE_URL = _build_db_url()

    @staticmethod
    def get_database_url():
        return _build_db_url()

    @staticmethod
    def get_db_config():
        return _build_db_url()

