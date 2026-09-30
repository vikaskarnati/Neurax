"""
Configuration module.
Loads environment variables and stores central configuration settings such as database credentials, JWT secrets, and API keys.
"""
import os
import urllib.parse
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

def _build_db_config():
    """Build MySQL connection dictionary from DATABASE_URL/MYSQL_URL or DB_* environment variables."""
    db_url = os.getenv('DATABASE_URL') or os.getenv('MYSQL_URL')
    if db_url:
        if db_url.startswith('mysql2://'):
            db_url = 'mysql://' + db_url[len('mysql2://'):]
        elif db_url.startswith('mysql+mysqlconnector://'):
            db_url = 'mysql://' + db_url[len('mysql+mysqlconnector://'):]

        parsed = urllib.parse.urlparse(db_url)
        query = urllib.parse.parse_qs(parsed.query)

        cfg = {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 3306,
            'user': urllib.parse.unquote(parsed.username) if parsed.username else 'root',
            'password': urllib.parse.unquote(parsed.password) if parsed.password else '',
            'database': parsed.path.lstrip('/') if parsed.path else 'neurax_db',
            'autocommit': True
        }

        if 'ssl_ca' in query:
            cfg['ssl_ca'] = query['ssl_ca'][0]
        if 'ssl_verify_cert' in query:
            val = query['ssl_verify_cert'][0].lower()
            cfg['ssl_verify_cert'] = val not in ('false', '0', 'no')
        if os.getenv('DB_SSL_CA'):
            cfg['ssl_ca'] = os.getenv('DB_SSL_CA')
        if os.getenv('DB_SSL_VERIFY_CERT'):
            val = os.getenv('DB_SSL_VERIFY_CERT', '').lower()
            cfg['ssl_verify_cert'] = val not in ('false', '0', 'no')
        if os.getenv('DB_SSL_DISABLED', '').lower() in ('true', '1', 'yes'):
            cfg['ssl_disabled'] = True
        elif os.getenv('DB_SSL_DISABLED', '').lower() in ('false', '0', 'no'):
            cfg['ssl_disabled'] = False
        return cfg

    port_str = os.getenv('DB_PORT', '3306')
    try:
        port = int(port_str)
    except (ValueError, TypeError):
        port = 3306

    cfg = {
        'host':       os.getenv('DB_HOST', 'localhost'),
        'port':       port,
        'user':       os.getenv('DB_USER', 'root'),
        'password':   os.getenv('DB_PASSWORD', ''),
        'database':   os.getenv('DB_NAME', 'neurax_db'),
        'autocommit': True
    }
    if os.getenv('DB_SSL_CA'):
        cfg['ssl_ca'] = os.getenv('DB_SSL_CA')
    if os.getenv('DB_SSL_VERIFY_CERT'):
        val = os.getenv('DB_SSL_VERIFY_CERT', '').lower()
        cfg['ssl_verify_cert'] = val not in ('false', '0', 'no')
    if os.getenv('DB_SSL_DISABLED', '').lower() in ('true', '1', 'yes'):
        cfg['ssl_disabled'] = True
    elif os.getenv('DB_SSL_DISABLED', '').lower() in ('false', '0', 'no'):
        cfg['ssl_disabled'] = False

    return cfg

class Config:
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'neurax-jwt-secret')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    GOOGLE_PLACES_KEY = os.getenv('GOOGLE_PLACES_KEY', '')
    MAIL_EMAIL = os.getenv('MAIL_EMAIL')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@neurax.com')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    DB_CONFIG = _build_db_config()

    @staticmethod
    def get_db_config():
        return _build_db_config()

