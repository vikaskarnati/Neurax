"""
Public routes blueprint.
Serves the main HTML templates (frontend views) and handles unprotected public API endpoints.
"""
from flask import Blueprint, render_template, jsonify, request
from config import Config
from database import get_db, patient_required

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    return render_template('index.html')

@public_bp.route('/auth')
def auth_page():
    return render_template('auth.html')

@public_bp.route('/patient')
def patient_page():
    return render_template('patient.html', google_places_key=Config.GOOGLE_PLACES_KEY)

@public_bp.route('/hospital')
def hospital_page():
    return render_template('hospital.html')

@public_bp.route('/admin')
def admin_page():
    return render_template('admin.html')

@public_bp.route('/api/doctors', methods=['GET'])
@patient_required
def get_doctors():
    specialization = request.args.get('specialization', '')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    if specialization:
        c.execute("""
            SELECT id, name, specialization, qualification, experience_years
            FROM doctors WHERE is_active=TRUE AND specialization=%s
            ORDER BY experience_years DESC
        """, (specialization,))
    else:
        c.execute("""
            SELECT id, name, specialization, qualification, experience_years
            FROM doctors WHERE is_active=TRUE ORDER BY specialization, experience_years DESC
        """)
    doctors = c.fetchall()
    conn.close()
    return jsonify(doctors)
