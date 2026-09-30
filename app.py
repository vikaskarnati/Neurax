"""
Main entry point for the NEURAX application.
Initializes the Flask app, loads configurations, registers routing blueprints, and starts the web server.
"""
import os
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from config import Config
from database import create_tables
from routes import register_blueprints

app = Flask(__name__)
CORS(app)

app.config.from_object(Config)

jwt = JWTManager(app)

register_blueprints(app)

# Auto-initialize database tables on startup if database is configured
try:
    create_tables()
except Exception as e:
    print(f"[STARTUP NOTICE] Database table auto-creation deferred or failed: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() in ('true', '1')
    app.run(host='0.0.0.0', port=port, debug=debug_mode)

