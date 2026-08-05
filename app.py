"""
Main entry point for the NEURAX application.
Initializes the Flask app, loads configurations, registers routing blueprints, and starts the web server.
"""
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

if __name__ == '__main__':
    create_tables()
    app.run(debug=True, port=5000)
