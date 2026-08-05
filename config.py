"""
Configuration module.
Loads environment variables and stores central configuration settings such as database credentials, JWT secrets, and API keys.
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'neurax-jwt-secret')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    GOOGLE_PLACES_KEY = os.getenv('GOOGLE_PLACES_KEY', '')
    MAIL_EMAIL = os.getenv('MAIL_EMAIL')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@neurax.com')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    DB_CONFIG = {
        'host':       os.getenv('DB_HOST', 'localhost'),
        'user':       os.getenv('DB_USER', 'root'),
        'password':   os.getenv('DB_PASSWORD', ''),
        'database':   os.getenv('DB_NAME', 'neurax_db'),
        'autocommit': True
    }
