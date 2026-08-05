"""
Blueprint registration module.
Aggregates all route blueprints and provides a single function to register them with the main Flask app.
"""
from routes.auth import auth_bp
from routes.patient import patient_bp
from routes.hospital import hospital_bp
from routes.admin import admin_bp
from routes.public import public_bp

def register_blueprints(app):
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(hospital_bp)
    app.register_blueprint(admin_bp)
