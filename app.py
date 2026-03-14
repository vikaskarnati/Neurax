import os
import uuid
import random
import string
import smtplib
import hashlib
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps

from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required,
    get_jwt_identity, get_jwt
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import mysql.connector
from google import genai

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.units import mm
import io

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'neurax-jwt-secret')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
jwt = JWTManager(app)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
MAIL_EMAIL = os.getenv('MAIL_EMAIL')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@neurax.com')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'neurax_db'),
    'autocommit': True
}

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def create_tables():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS hospitals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            type VARCHAR(100),
            registration_number VARCHAR(100),
            hospital_code VARCHAR(20) UNIQUE NOT NULL,
            status ENUM('pending','approved','rejected') DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS branches (
            id INT AUTO_INCREMENT PRIMARY KEY,
            hospital_id INT NOT NULL,
            name VARCHAR(200) NOT NULL,
            address TEXT,
            city VARCHAR(100),
            state VARCHAR(100),
            phone VARCHAR(20),
            email VARCHAR(150) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            is_primary BOOLEAN DEFAULT FALSE,
            status ENUM('pending','approved','rejected') DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS branch_invites (
            id INT AUTO_INCREMENT PRIMARY KEY,
            hospital_id INT NOT NULL,
            inviting_branch_id INT NOT NULL,
            invite_token VARCHAR(64) UNIQUE NOT NULL,
            email VARCHAR(150) NOT NULL,
            status ENUM('pending','used','expired') DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id),
            FOREIGN KEY (inviting_branch_id) REFERENCES branches(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patient_uid VARCHAR(20) UNIQUE NOT NULL,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            phone VARCHAR(20),
            dob DATE,
            gender ENUM('male','female','other'),
            blood_group VARCHAR(5),
            emergency_contact_name VARCHAR(100),
            emergency_contact_phone VARCHAR(20),
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patient_id INT NOT NULL,
            branch_id INT NOT NULL,
            appointment_date DATE NOT NULL,
            appointment_time VARCHAR(10) NOT NULL,
            reason TEXT,
            status ENUM('pending','confirmed','completed','cancelled') DEFAULT 'pending',
            confirmation_number VARCHAR(20) UNIQUE NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (branch_id) REFERENCES branches(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS medical_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            appointment_id INT NOT NULL,
            branch_id INT NOT NULL,
            patient_id INT NOT NULL,
            diagnosis TEXT,
            prescription TEXT,
            notes TEXT,
            vitals JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (appointment_id) REFERENCES appointments(id),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (branch_id) REFERENCES branches(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS cross_hospital_access (
            id INT AUTO_INCREMENT PRIMARY KEY,
            requesting_hospital_id INT NOT NULL,
            granting_hospital_id INT NOT NULL,
            requesting_branch_id INT NOT NULL,
            granting_branch_id INT,
            status ENUM('pending','granted','revoked') DEFAULT 'pending',
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            granted_at TIMESTAMP NULL,
            revoked_at TIMESTAMP NULL,
            FOREIGN KEY (requesting_hospital_id) REFERENCES hospitals(id),
            FOREIGN KEY (granting_hospital_id) REFERENCES hospitals(id),
            FOREIGN KEY (requesting_branch_id) REFERENCES branches(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            recipient_type ENUM('patient','branch','admin') NOT NULL,
            recipient_id INT NOT NULL,
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            type VARCHAR(50),
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_otps (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(150) NOT NULL,
            user_type ENUM('patient','branch') NOT NULL,
            otp_hash VARCHAR(64) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patient_id INT NOT NULL,
            session_id VARCHAR(64) NOT NULL,
            role ENUM('user','assistant') NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            actor_type ENUM('patient','branch','admin') NOT NULL,
            actor_id INT NOT NULL,
            action VARCHAR(100) NOT NULL,
            target_type VARCHAR(50),
            target_id INT,
            details JSON,
            ip_address VARCHAR(45),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.close()
    print("Database tables ready.")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def generate_patient_uid():
    return "PAT-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def generate_hospital_code():
    return "HOSP-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def generate_confirmation_number():
    return "CONF-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def generate_otp():
    return str(random.randint(100000, 999999))

def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()

def send_email(to_email, subject, html_body):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = MAIL_EMAIL
        msg['To'] = to_email
        msg.attach(MIMEText(html_body, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(MAIL_EMAIL, MAIL_PASSWORD)
            server.sendmail(MAIL_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def add_notification(recipient_type, recipient_id, title, message, notif_type=None):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO notifications (recipient_type, recipient_id, title, message, type)
            VALUES (%s, %s, %s, %s, %s)
        """, (recipient_type, recipient_id, title, message, notif_type))
        conn.close()
    except Exception as e:
        print(f"Notification error: {e}")

def log_audit(actor_type, actor_id, action, target_type=None, target_id=None, details=None, ip=None):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO audit_logs (actor_type, actor_id, action, target_type, target_id, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (actor_type, actor_id, action, target_type, target_id,
              json.dumps(details) if details else None, ip))
        conn.close()
    except Exception as e:
        print(f"Audit log error: {e}")

def serialize(obj):
    if isinstance(obj, list):
        return [serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj

def branch_required(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        claims = get_jwt()
        if claims.get('role') != 'branch':
            return jsonify({'error': 'Branch access required'}), 403
        return f(*args, **kwargs)
    return decorated

def patient_required(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        claims = get_jwt()
        if claims.get('role') != 'patient':
            return jsonify({'error': 'Patient access required'}), 403
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        claims = get_jwt()
        if claims.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
# PAGE ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth')
def auth_page():
    return render_template('auth.html')

@app.route('/patient')
def patient_page():
    return render_template('patient.html')

@app.route('/branch')
def branch_page():
    return render_template('branch.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

# ─────────────────────────────────────────────
# AUTH — PATIENT
# ─────────────────────────────────────────────

@app.route('/api/auth/patient/register', methods=['POST'])
def patient_register():
    data = request.json
    required = ['first_name', 'last_name', 'email', 'password', 'phone', 'dob', 'gender', 'blood_group']
    if not all(data.get(f) for f in required):
        return jsonify({'error': 'All fields are required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id FROM patients WHERE email = %s", (data['email'],))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Email already registered'}), 409

    uid = generate_patient_uid()
    while True:
        c.execute("SELECT id FROM patients WHERE patient_uid = %s", (uid,))
        if not c.fetchone():
            break
        uid = generate_patient_uid()

    c.execute("""
        INSERT INTO patients (patient_uid, first_name, last_name, email, password_hash,
            phone, dob, gender, blood_group, emergency_contact_name, emergency_contact_phone, address)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        uid, data['first_name'], data['last_name'], data['email'],
        generate_password_hash(data['password']), data['phone'], data['dob'],
        data['gender'], data['blood_group'],
        data.get('emergency_contact_name'), data.get('emergency_contact_phone'),
        data.get('address')
    ))
    patient_id = c.lastrowid
    conn.close()

    token = create_access_token(
        identity=str(patient_id),
        additional_claims={'role': 'patient', 'uid': uid}
    )

    send_email(data['email'], 'Welcome to NEURAX', f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto;padding:32px">
        <h2 style="color:#007AFF;margin-bottom:4px">Welcome to NEURAX</h2>
        <p>Hi {data['first_name']}, your account is ready.</p>
        <div style="background:#F2F2F7;border-radius:12px;padding:16px;margin:16px 0">
            <p style="margin:0;color:#8E8E93;font-size:12px">YOUR PATIENT ID</p>
            <p style="margin:4px 0 0;font-size:22px;font-weight:700;letter-spacing:2px">{uid}</p>
        </div>
        <p style="color:#8E8E93;font-size:13px">Keep this ID safe — it identifies you across all hospitals on NEURAX.</p>
    </div>
    """)

    return jsonify({'token': token, 'patient_uid': uid, 'first_name': data['first_name']}), 201


@app.route('/api/auth/patient/login', methods=['POST'])
def patient_login():
    data = request.json
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM patients WHERE email = %s", (data['email'],))
    patient = c.fetchone()
    conn.close()

    if not patient or not check_password_hash(patient['password_hash'], data['password']):
        return jsonify({'error': 'Invalid email or password'}), 401

    token = create_access_token(
        identity=str(patient['id']),
        additional_claims={'role': 'patient', 'uid': patient['patient_uid']}
    )
    return jsonify({
        'token': token,
        'patient_uid': patient['patient_uid'],
        'first_name': patient['first_name'],
        'last_name': patient['last_name']
    })

# ─────────────────────────────────────────────
# AUTH — BRANCH
# ─────────────────────────────────────────────

@app.route('/api/auth/branch/register', methods=['POST'])
def branch_register():
    data = request.json
    required = ['hospital_name', 'hospital_type', 'registration_number',
                'branch_name', 'address', 'city', 'state', 'phone', 'email', 'password']
    if not all(data.get(f) for f in required):
        return jsonify({'error': 'All fields are required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id FROM branches WHERE email = %s", (data['email'],))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Email already registered'}), 409

    hospital_code = generate_hospital_code()
    while True:
        c.execute("SELECT id FROM hospitals WHERE hospital_code = %s", (hospital_code,))
        if not c.fetchone():
            break
        hospital_code = generate_hospital_code()

    c.execute("""
        INSERT INTO hospitals (name, type, registration_number, hospital_code, status)
        VALUES (%s, %s, %s, %s, 'pending')
    """, (data['hospital_name'], data['hospital_type'], data['registration_number'], hospital_code))
    hospital_id = c.lastrowid

    c.execute("""
        INSERT INTO branches (hospital_id, name, address, city, state, phone, email, password_hash, is_primary, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, 'pending')
    """, (hospital_id, data['branch_name'], data['address'], data['city'],
          data['state'], data['phone'], data['email'],
          generate_password_hash(data['password'])))
    conn.close()

    send_email(ADMIN_EMAIL, f'New Hospital Registration: {data["hospital_name"]}', f"""
    <div style="font-family:sans-serif;padding:24px">
        <h2>New Hospital Registration</h2>
        <p><strong>Hospital:</strong> {data['hospital_name']} ({data['hospital_type']})</p>
        <p><strong>Reg No:</strong> {data['registration_number']}</p>
        <p><strong>Branch:</strong> {data['branch_name']}, {data['city']}, {data['state']}</p>
        <p><strong>Contact:</strong> {data['email']} | {data['phone']}</p>
        <p>Login to the admin panel to approve or reject.</p>
    </div>
    """)

    return jsonify({
        'message': 'Registration submitted. Awaiting admin approval.',
        'hospital_code': hospital_code
    }), 201


@app.route('/api/auth/branch/register-via-invite', methods=['POST'])
def branch_register_invite():
    data = request.json
    required = ['invite_token', 'branch_name', 'address', 'city', 'state', 'phone', 'email', 'password']
    if not all(data.get(f) for f in required):
        return jsonify({'error': 'All fields are required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT * FROM branch_invites
        WHERE invite_token = %s AND status = 'pending' AND expires_at > NOW()
    """, (data['invite_token'],))
    invite = c.fetchone()
    if not invite:
        conn.close()
        return jsonify({'error': 'Invalid or expired invite token'}), 400

    c.execute("SELECT id FROM branches WHERE email = %s", (data['email'],))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Email already registered'}), 409

    c.execute("""
        INSERT INTO branches (hospital_id, name, address, city, state, phone, email, password_hash, is_primary, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE, 'approved')
    """, (invite['hospital_id'], data['branch_name'], data['address'], data['city'],
          data['state'], data['phone'], data['email'],
          generate_password_hash(data['password'])))
    branch_id = c.lastrowid

    c.execute("UPDATE branch_invites SET status = 'used' WHERE id = %s", (invite['id'],))
    conn.close()

    token = create_access_token(
        identity=str(branch_id),
        additional_claims={'role': 'branch', 'hospital_id': invite['hospital_id']}
    )
    return jsonify({'token': token, 'message': 'Branch registered successfully'}), 201


@app.route('/api/auth/branch/login', methods=['POST'])
def branch_login():
    data = request.json
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT b.*, h.name as hospital_name, h.hospital_code, h.status as hospital_status
        FROM branches b JOIN hospitals h ON b.hospital_id = h.id
        WHERE b.email = %s
    """, (data['email'],))
    branch = c.fetchone()
    conn.close()

    if not branch or not check_password_hash(branch['password_hash'], data['password']):
        return jsonify({'error': 'Invalid email or password'}), 401
    if branch['status'] != 'approved':
        return jsonify({'error': 'Your branch is pending approval'}), 403

    token = create_access_token(
        identity=str(branch['id']),
        additional_claims={'role': 'branch', 'hospital_id': branch['hospital_id']}
    )
    return jsonify({
        'token': token,
        'branch_name': branch['name'],
        'hospital_name': branch['hospital_name'],
        'hospital_code': branch['hospital_code'],
        'city': branch['city']
    })

# ─────────────────────────────────────────────
# AUTH — ADMIN
# ─────────────────────────────────────────────

@app.route('/api/auth/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    if data.get('email') != ADMIN_EMAIL or data.get('password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Invalid credentials'}), 401
    token = create_access_token(identity='admin', additional_claims={'role': 'admin'})
    return jsonify({'token': token})

# ─────────────────────────────────────────────
# AUTH — PASSWORD RESET
# ─────────────────────────────────────────────

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json
    email = data.get('email')
    user_type = data.get('user_type')
    if not email or not user_type:
        return jsonify({'error': 'Email and user_type required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    if user_type == 'patient':
        c.execute("SELECT id FROM patients WHERE email = %s", (email,))
    else:
        c.execute("SELECT id FROM branches WHERE email = %s", (email,))
    user = c.fetchone()

    if user:
        otp = generate_otp()
        expires_at = datetime.now() + timedelta(minutes=10)
        c.execute("""
            INSERT INTO password_reset_otps (email, user_type, otp_hash, expires_at)
            VALUES (%s, %s, %s, %s)
        """, (email, user_type, hash_otp(otp), expires_at))

        send_email(email, 'NEURAX — Password Reset OTP', f"""
        <div style="font-family:sans-serif;max-width:500px;margin:auto;padding:32px">
            <h2 style="color:#007AFF">Password Reset</h2>
            <p>Your OTP is:</p>
            <div style="font-size:40px;font-weight:700;letter-spacing:10px;color:#1C1C1E;
                        background:#F2F2F7;padding:20px;border-radius:16px;text-align:center;margin:16px 0">
                {otp}
            </div>
            <p style="color:#8E8E93;font-size:13px">Expires in 10 minutes. Do not share this with anyone.</p>
        </div>
        """)
    conn.close()
    return jsonify({'message': 'If this email exists, an OTP has been sent'}), 200


@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    email, otp, new_password, user_type = (
        data.get('email'), data.get('otp'),
        data.get('new_password'), data.get('user_type')
    )
    if not all([email, otp, new_password, user_type]):
        return jsonify({'error': 'All fields required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT * FROM password_reset_otps
        WHERE email = %s AND user_type = %s AND otp_hash = %s
          AND used = FALSE AND expires_at > NOW()
        ORDER BY created_at DESC LIMIT 1
    """, (email, user_type, hash_otp(otp)))
    record = c.fetchone()

    if not record:
        conn.close()
        return jsonify({'error': 'Invalid or expired OTP'}), 400

    new_hash = generate_password_hash(new_password)
    if user_type == 'patient':
        c.execute("UPDATE patients SET password_hash = %s WHERE email = %s", (new_hash, email))
    else:
        c.execute("UPDATE branches SET password_hash = %s WHERE email = %s", (new_hash, email))
    c.execute("UPDATE password_reset_otps SET used = TRUE WHERE id = %s", (record['id'],))
    conn.close()
    return jsonify({'message': 'Password reset successfully'})

# ─────────────────────────────────────────────
# PATIENT — PROFILE & CARD
# ─────────────────────────────────────────────

@app.route('/api/patient/profile', methods=['GET'])
@patient_required
def get_patient_profile():
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT id, patient_uid, first_name, last_name, email, phone, dob, gender,
               blood_group, emergency_contact_name, emergency_contact_phone, address, created_at
        FROM patients WHERE id = %s
    """, (patient_id,))
    patient = c.fetchone()
    conn.close()
    return jsonify(serialize(patient))


@app.route('/api/patient/profile', methods=['PUT'])
@patient_required
def update_patient_profile():
    patient_id = get_jwt_identity()
    data = request.json
    allowed = ['first_name', 'last_name', 'phone', 'dob', 'gender', 'blood_group',
               'emergency_contact_name', 'emergency_contact_phone', 'address']
    updates = {k: data[k] for k in allowed if k in data}
    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400
    set_clause = ', '.join(f"{k} = %s" for k in updates)
    conn = get_db()
    c = conn.cursor()
    c.execute(f"UPDATE patients SET {set_clause} WHERE id = %s", list(updates.values()) + [patient_id])
    conn.close()
    return jsonify({'message': 'Profile updated'})


@app.route('/api/patient/card', methods=['GET'])
@patient_required
def get_patient_card():
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT id, patient_uid, first_name, last_name, email, phone, dob, gender,
               blood_group, emergency_contact_name, emergency_contact_phone, address, created_at
        FROM patients WHERE id = %s
    """, (patient_id,))
    patient = c.fetchone()
    c.execute("""
        SELECT a.*, b.name as branch_name, b.city, b.phone as branch_phone, h.name as hospital_name
        FROM appointments a
        JOIN branches b ON a.branch_id = b.id
        JOIN hospitals h ON b.hospital_id = h.id
        WHERE a.patient_id = %s ORDER BY a.created_at DESC LIMIT 5
    """, (patient_id,))
    recent_appointments = c.fetchall()
    c.execute("""
        SELECT mr.*, b.name as branch_name, h.name as hospital_name
        FROM medical_records mr
        JOIN branches b ON mr.branch_id = b.id
        JOIN hospitals h ON b.hospital_id = h.id
        WHERE mr.patient_id = %s ORDER BY mr.created_at DESC LIMIT 3
    """, (patient_id,))
    recent_records = c.fetchall()
    conn.close()
    return jsonify({
        'patient': serialize(patient),
        'recent_appointments': serialize(recent_appointments),
        'recent_records': serialize(recent_records)
    })


@app.route('/api/patient/card/pdf', methods=['GET'])
@patient_required
def download_patient_card_pdf():
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
    patient = c.fetchone()
    c.execute("""
        SELECT a.*, b.name as branch_name, b.city, h.name as hospital_name
        FROM appointments a
        JOIN branches b ON a.branch_id = b.id
        JOIN hospitals h ON b.hospital_id = h.id
        WHERE a.patient_id = %s ORDER BY a.created_at DESC LIMIT 5
    """, (patient_id,))
    appointments = c.fetchall()
    conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('T', parent=styles['Title'],
                                 textColor=colors.HexColor('#007AFF'), fontSize=24, spaceAfter=4)
    sub_style = ParagraphStyle('S', parent=styles['Normal'],
                               textColor=colors.HexColor('#8E8E93'), fontSize=11, spaceAfter=12)
    heading_style = ParagraphStyle('H', parent=styles['Heading2'],
                                   textColor=colors.HexColor('#1C1C1E'), fontSize=13, spaceBefore=14, spaceAfter=6)
    footer_style = ParagraphStyle('F', parent=styles['Normal'],
                                  fontSize=8, textColor=colors.HexColor('#8E8E93'), alignment=1)

    story = [
        Paragraph("NEURAX HEALTH", title_style),
        Paragraph("Patient Health Card", sub_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E5E5EA')),
        Spacer(1, 5*mm),
    ]

    info = [
        ['Patient Name', f"{patient['first_name']} {patient['last_name']}", 'Patient UID', patient['patient_uid']],
        ['Date of Birth', str(patient['dob'])[:10] if patient.get('dob') else 'N/A', 'Gender', (patient.get('gender') or 'N/A').title()],
        ['Blood Group', patient.get('blood_group') or 'N/A', 'Phone', patient.get('phone') or 'N/A'],
        ['Email', patient['email'], 'Member Since', str(patient['created_at'])[:10]],
        ['Emergency Contact', patient.get('emergency_contact_name') or 'N/A', 'Emergency Phone', patient.get('emergency_contact_phone') or 'N/A'],
    ]
    t = Table(info, colWidths=[38*mm, 62*mm, 38*mm, 62*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#8E8E93')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#8E8E93')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#F9F9F9'), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E5EA')),
        ('PADDING', (0, 0), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t)

    if appointments:
        story.append(Paragraph("Appointment History", heading_style))
        rows = [['Hospital', 'Branch', 'Date', 'Time', 'Status']]
        for a in appointments:
            rows.append([
                a.get('hospital_name', ''),
                a.get('branch_name', ''),
                str(a.get('appointment_date', ''))[:10],
                a.get('appointment_time', ''),
                (a.get('status', '')).title()
            ])
        at = Table(rows, colWidths=[44*mm, 44*mm, 28*mm, 24*mm, 28*mm])
        at.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007AFF')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9F9F9')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E5EA')),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(at)

    story += [
        Spacer(1, 10*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E5E5EA')),
        Spacer(1, 3*mm),
        Paragraph(f"Generated by NEURAX Health Platform  •  {datetime.now().strftime('%d %b %Y, %I:%M %p')}", footer_style)
    ]

    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name=f"patient_card_{patient['patient_uid']}.pdf",
                     mimetype='application/pdf')

# ─────────────────────────────────────────────
# PATIENT — APPOINTMENTS
# ─────────────────────────────────────────────

@app.route('/api/patient/appointments', methods=['GET'])
@patient_required
def get_patient_appointments():
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT a.*, b.name as branch_name, b.city, b.phone as branch_phone, h.name as hospital_name
        FROM appointments a
        JOIN branches b ON a.branch_id = b.id
        JOIN hospitals h ON b.hospital_id = h.id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """, (patient_id,))
    appts = c.fetchall()
    conn.close()
    return jsonify(serialize(appts))


@app.route('/api/patient/appointments/book', methods=['POST'])
@patient_required
def book_appointment():
    patient_id = get_jwt_identity()
    data = request.json
    required = ['branch_id', 'appointment_date', 'appointment_time', 'reason']
    if not all(data.get(f) for f in required):
        return jsonify({'error': 'All fields required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id, status FROM branches WHERE id = %s", (data['branch_id'],))
    branch = c.fetchone()
    if not branch or branch['status'] != 'approved':
        conn.close()
        return jsonify({'error': 'Branch not found or not approved'}), 404

    conf = generate_confirmation_number()
    while True:
        c.execute("SELECT id FROM appointments WHERE confirmation_number = %s", (conf,))
        if not c.fetchone():
            break
        conf = generate_confirmation_number()

    c.execute("""
        INSERT INTO appointments (patient_id, branch_id, appointment_date, appointment_time, reason, confirmation_number)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (patient_id, data['branch_id'], data['appointment_date'],
          data['appointment_time'], data['reason'], conf))

    c.execute("""
        SELECT b.name as branch_name, b.city, h.name as hospital_name
        FROM branches b JOIN hospitals h ON b.hospital_id = h.id WHERE b.id = %s
    """, (data['branch_id'],))
    branch_info = c.fetchone()
    c.execute("SELECT first_name, last_name, email FROM patients WHERE id = %s", (patient_id,))
    patient = c.fetchone()
    conn.close()

    add_notification('patient', patient_id, 'Appointment Booked',
                     f"Appointment at {branch_info['branch_name']} on {data['appointment_date']} submitted.", 'appointment')
    add_notification('branch', data['branch_id'], 'New Appointment',
                     f"{patient['first_name']} {patient['last_name']} booked for {data['appointment_date']}.", 'appointment')

    send_email(patient['email'], f'Appointment Submitted — {conf}', f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto;padding:32px">
        <h2 style="color:#007AFF">Appointment Submitted</h2>
        <p>Hi {patient['first_name']}, your appointment has been submitted.</p>
        <div style="background:#F2F2F7;border-radius:12px;padding:16px;margin:16px 0">
            <table style="width:100%;border-collapse:collapse">
                <tr><td style="color:#8E8E93;padding:4px 0;font-size:13px">Confirmation</td>
                    <td style="font-weight:700;padding:4px 0">{conf}</td></tr>
                <tr><td style="color:#8E8E93;padding:4px 0;font-size:13px">Hospital</td>
                    <td style="padding:4px 0">{branch_info['hospital_name']}</td></tr>
                <tr><td style="color:#8E8E93;padding:4px 0;font-size:13px">Branch</td>
                    <td style="padding:4px 0">{branch_info['branch_name']}, {branch_info['city']}</td></tr>
                <tr><td style="color:#8E8E93;padding:4px 0;font-size:13px">Date & Time</td>
                    <td style="padding:4px 0">{data['appointment_date']} at {data['appointment_time']}</td></tr>
                <tr><td style="color:#8E8E93;padding:4px 0;font-size:13px">Reason</td>
                    <td style="padding:4px 0">{data['reason']}</td></tr>
            </table>
        </div>
        <p style="color:#8E8E93;font-size:12px">NEURAX Health Platform</p>
    </div>
    """)
    return jsonify({'message': 'Appointment booked', 'confirmation_number': conf}), 201

# ─────────────────────────────────────────────
# PATIENT — HOSPITALS & HISTORY
# ─────────────────────────────────────────────

@app.route('/api/patient/hospitals', methods=['GET'])
@patient_required
def get_hospitals():
    search = request.args.get('search', '')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    query = """
        SELECT h.id, h.name, h.type, h.hospital_code, COUNT(b.id) as branch_count
        FROM hospitals h
        LEFT JOIN branches b ON h.id = b.hospital_id AND b.status = 'approved'
        WHERE h.status = 'approved'
    """
    params = []
    if search:
        query += " AND h.name LIKE %s"
        params.append(f"%{search}%")
    query += " GROUP BY h.id ORDER BY h.name"
    c.execute(query, params)
    hospitals = c.fetchall()
    conn.close()
    return jsonify(hospitals)


@app.route('/api/patient/hospitals/<int:hospital_id>/branches', methods=['GET'])
@patient_required
def get_hospital_branches(hospital_id):
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT id, name, address, city, state, phone
        FROM branches WHERE hospital_id = %s AND status = 'approved'
    """, (hospital_id,))
    branches = c.fetchall()
    conn.close()
    return jsonify(branches)


@app.route('/api/patient/medical-history', methods=['GET'])
@patient_required
def get_patient_medical_history():
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT mr.*, a.appointment_date, a.appointment_time, a.reason,
               b.name as branch_name, h.name as hospital_name
        FROM medical_records mr
        JOIN appointments a ON mr.appointment_id = a.id
        JOIN branches b ON mr.branch_id = b.id
        JOIN hospitals h ON b.hospital_id = h.id
        WHERE mr.patient_id = %s ORDER BY mr.created_at DESC
    """, (patient_id,))
    records = c.fetchall()
    conn.close()
    return jsonify(serialize(records))

# ─────────────────────────────────────────────
# PATIENT — NOTIFICATIONS
# ─────────────────────────────────────────────

@app.route('/api/patient/notifications', methods=['GET'])
@patient_required
def get_patient_notifications():
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT * FROM notifications
        WHERE recipient_type = 'patient' AND recipient_id = %s
        ORDER BY created_at DESC LIMIT 50
    """, (patient_id,))
    notifs = c.fetchall()
    conn.close()
    return jsonify(serialize(notifs))


@app.route('/api/patient/notifications/<int:notif_id>/read', methods=['PUT'])
@patient_required
def mark_patient_notification_read(notif_id):
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE notifications SET is_read = TRUE
        WHERE id = %s AND recipient_type = 'patient' AND recipient_id = %s
    """, (notif_id, patient_id))
    conn.close()
    return jsonify({'message': 'Marked as read'})

# ─────────────────────────────────────────────
# PATIENT — AI CHAT
# ─────────────────────────────────────────────

@app.route('/api/chat', methods=['POST'])
@patient_required
def ai_chat():
    patient_id = get_jwt_identity()
    data = request.json
    message = data.get('message', '').strip()
    session_id = data.get('session_id', str(uuid.uuid4()))
    mode = data.get('mode', 'general')
    if not message:
        return jsonify({'error': 'Message is required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT first_name, last_name, dob, gender, blood_group FROM patients WHERE id = %s", (patient_id,))
    patient = c.fetchone()

    c.execute("""
        SELECT mr.diagnosis, mr.prescription, a.appointment_date, b.name as branch_name
        FROM medical_records mr
        JOIN appointments a ON mr.appointment_id = a.id
        JOIN branches b ON mr.branch_id = b.id
        WHERE mr.patient_id = %s ORDER BY mr.created_at DESC LIMIT 5
    """, (patient_id,))
    records = c.fetchall()

    c.execute("""
        SELECT role, message FROM conversations
        WHERE patient_id = %s AND session_id = %s
        ORDER BY created_at DESC LIMIT 10
    """, (patient_id, session_id))
    history = list(reversed(c.fetchall()))

    age = None
    if patient and patient.get('dob'):
        age = (datetime.now().date() - patient['dob']).days // 365

    context = []
    if patient:
        context.append(f"Patient: {patient['first_name']} {patient['last_name']}, Age: {age or 'Unknown'}, Gender: {patient.get('gender','Unknown')}, Blood Group: {patient.get('blood_group','Unknown')}")
    if records:
        context.append("Recent Medical History:")
        for r in records:
            context.append(f"- {str(r.get('appointment_date',''))[:10]} at {r.get('branch_name','')}: Diagnosis: {r.get('diagnosis','N/A')}, Prescription: {r.get('prescription','N/A')}")

    mode_prompts = {
        'general': "You are a helpful medical assistant. Provide clear, concise, practical health information. Always recommend consulting a doctor for serious concerns.",
        'symptoms': "You are a symptom analysis assistant. Assess the described symptoms, list possible causes, and indicate urgency level (low/medium/high). Always recommend professional evaluation.",
        'medication': "You are a medication information assistant. Provide accurate medication details including dosages, side effects, and interactions. Always advise medical supervision.",
        'health': "You are a wellness advisor. Provide preventive health tips and lifestyle guidance in clear bullet points."
    }
    system_prompt = mode_prompts.get(mode, mode_prompts['general'])
    if context:
        system_prompt += "\n\nPatient Context:\n" + "\n".join(context)

    history_text = "\n".join(f"{h['role'].title()}: {h['message']}" for h in history[-6:])
    full_prompt = f"{history_text}\nUser: {message}" if history_text else message

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[{'role': 'user', 'parts': [{'text': system_prompt + '\n\n' + full_prompt}]}]
        )
        reply = response.text

        c.execute("INSERT INTO conversations (patient_id, session_id, role, message) VALUES (%s,%s,'user',%s)",
                  (patient_id, session_id, message))
        c.execute("INSERT INTO conversations (patient_id, session_id, role, message) VALUES (%s,%s,'assistant',%s)",
                  (patient_id, session_id, reply))
        conn.close()
        return jsonify({'reply': reply, 'session_id': session_id})
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat/sessions', methods=['GET'])
@patient_required
def get_chat_sessions():
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT session_id, MIN(created_at) as started_at,
               SUBSTRING(MIN(message), 1, 60) as preview
        FROM conversations WHERE patient_id = %s AND role = 'user'
        GROUP BY session_id ORDER BY started_at DESC LIMIT 20
    """, (patient_id,))
    sessions = c.fetchall()
    conn.close()
    return jsonify(serialize(sessions))


@app.route('/api/chat/sessions/<session_id>', methods=['GET'])
@patient_required
def get_chat_session(session_id):
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT role, message, created_at FROM conversations
        WHERE patient_id = %s AND session_id = %s ORDER BY created_at ASC
    """, (patient_id, session_id))
    messages = c.fetchall()
    conn.close()
    return jsonify(serialize(messages))

# ─────────────────────────────────────────────
# BRANCH — PROFILE & STATS
# ─────────────────────────────────────────────

@app.route('/api/branch/profile', methods=['GET'])
@branch_required
def get_branch_profile():
    branch_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT b.id, b.name, b.address, b.city, b.state, b.phone, b.email,
               b.is_primary, b.status, b.created_at,
               h.name as hospital_name, h.type as hospital_type,
               h.hospital_code, h.registration_number
        FROM branches b JOIN hospitals h ON b.hospital_id = h.id WHERE b.id = %s
    """, (branch_id,))
    branch = c.fetchone()
    conn.close()
    return jsonify(serialize(branch))


@app.route('/api/branch/dashboard/stats', methods=['GET'])
@branch_required
def get_branch_stats():
    branch_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT COUNT(*) as total FROM appointments WHERE branch_id = %s", (branch_id,))
    total = c.fetchone()['total']
    c.execute("SELECT COUNT(*) as total FROM appointments WHERE branch_id = %s AND status='pending'", (branch_id,))
    pending = c.fetchone()['total']
    c.execute("SELECT COUNT(*) as total FROM appointments WHERE branch_id = %s AND appointment_date=CURDATE()", (branch_id,))
    today = c.fetchone()['total']
    c.execute("SELECT COUNT(DISTINCT patient_id) as total FROM appointments WHERE branch_id = %s", (branch_id,))
    patients = c.fetchone()['total']
    c.execute("""
        SELECT DATE(appointment_date) as date, COUNT(*) as count
        FROM appointments WHERE branch_id = %s
        AND appointment_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        GROUP BY DATE(appointment_date) ORDER BY date
    """, (branch_id,))
    weekly = c.fetchall()
    conn.close()

    return jsonify({
        'total_appointments': total,
        'pending_appointments': pending,
        'today_appointments': today,
        'unique_patients': patients,
        'weekly_chart': serialize(weekly)
    })

# ─────────────────────────────────────────────
# BRANCH — APPOINTMENTS
# ─────────────────────────────────────────────

@app.route('/api/branch/appointments', methods=['GET'])
@branch_required
def get_branch_appointments():
    branch_id = get_jwt_identity()
    status = request.args.get('status', '')
    date = request.args.get('date', '')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    query = """
        SELECT a.*, p.first_name, p.last_name, p.patient_uid,
               p.phone as patient_phone, p.blood_group, p.gender, p.dob
        FROM appointments a JOIN patients p ON a.patient_id = p.id
        WHERE a.branch_id = %s
    """
    params = [branch_id]
    if status:
        query += " AND a.status = %s"; params.append(status)
    if date:
        query += " AND a.appointment_date = %s"; params.append(date)
    query += " ORDER BY a.appointment_date DESC, a.appointment_time DESC"
    c.execute(query, params)
    appts = c.fetchall()
    conn.close()
    return jsonify(serialize(appts))


@app.route('/api/branch/appointments/<int:appt_id>/status', methods=['PUT'])
@branch_required
def update_appointment_status(appt_id):
    branch_id = get_jwt_identity()
    data = request.json
    new_status = data.get('status')
    if new_status not in ['confirmed', 'completed', 'cancelled']:
        return jsonify({'error': 'Invalid status'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM appointments WHERE id = %s AND branch_id = %s", (appt_id, branch_id))
    appt = c.fetchone()
    if not appt:
        conn.close()
        return jsonify({'error': 'Appointment not found'}), 404

    c.execute("UPDATE appointments SET status = %s, notes = %s WHERE id = %s",
              (new_status, data.get('notes'), appt_id))
    c.execute("SELECT first_name, last_name, email FROM patients WHERE id = %s", (appt['patient_id'],))
    patient = c.fetchone()
    conn.close()

    label = new_status.title()
    color = {'confirmed': '#34C759', 'completed': '#007AFF', 'cancelled': '#FF3B30'}.get(new_status, '#007AFF')
    add_notification('patient', appt['patient_id'], f'Appointment {label}',
                     f"Your appointment on {str(appt['appointment_date'])[:10]} has been {new_status}.", 'appointment')
    send_email(patient['email'], f'Appointment {label} — {appt["confirmation_number"]}', f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto;padding:32px">
        <h2 style="color:{color}">Appointment {label}</h2>
        <p>Hi {patient['first_name']}, your appointment <strong>{appt['confirmation_number']}</strong>
        on {str(appt['appointment_date'])[:10]} at {appt['appointment_time']} is now <strong>{new_status}</strong>.</p>
        {f'<p><strong>Notes:</strong> {data.get("notes")}</p>' if data.get('notes') else ''}
        <p style="color:#8E8E93;font-size:12px">NEURAX Health Platform</p>
    </div>
    """)
    return jsonify({'message': f'Appointment {new_status}'})

# ─────────────────────────────────────────────
# BRANCH — PATIENTS & RECORDS
# ─────────────────────────────────────────────

@app.route('/api/branch/patients', methods=['GET'])
@branch_required
def get_branch_patients():
    branch_id = get_jwt_identity()
    search = request.args.get('search', '')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    query = """
        SELECT DISTINCT p.id, p.patient_uid, p.first_name, p.last_name,
               p.phone, p.gender, p.blood_group, p.dob,
               MAX(a.appointment_date) as last_visit
        FROM patients p JOIN appointments a ON p.id = a.patient_id
        WHERE a.branch_id = %s
    """
    params = [branch_id]
    if search:
        query += " AND (p.first_name LIKE %s OR p.last_name LIKE %s OR p.patient_uid LIKE %s)"
        params.extend([f"%{search}%"] * 3)
    query += " GROUP BY p.id ORDER BY last_visit DESC"
    c.execute(query, params)
    patients = c.fetchall()
    conn.close()
    return jsonify(serialize(patients))


@app.route('/api/branch/patients/<int:pid>/records', methods=['GET'])
@branch_required
def get_patient_records_branch(pid):
    branch_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id FROM appointments WHERE patient_id = %s AND branch_id = %s", (pid, branch_id))
    if not c.fetchone():
        conn.close()
        return jsonify({'error': 'Patient not found in this branch'}), 404

    c.execute("""
        SELECT id, patient_uid, first_name, last_name, email, phone, dob, gender,
               blood_group, emergency_contact_name, emergency_contact_phone
        FROM patients WHERE id = %s
    """, (pid,))
    patient = c.fetchone()

    c.execute("""
        SELECT a.*, b.name as branch_name, h.name as hospital_name
        FROM appointments a
        JOIN branches b ON a.branch_id = b.id
        JOIN hospitals h ON b.hospital_id = h.id
        WHERE a.patient_id = %s AND a.branch_id = %s ORDER BY a.appointment_date DESC
    """, (pid, branch_id))
    appointments = c.fetchall()

    c.execute("""
        SELECT mr.*, a.appointment_date, a.reason
        FROM medical_records mr JOIN appointments a ON mr.appointment_id = a.id
        WHERE mr.patient_id = %s AND mr.branch_id = %s ORDER BY mr.created_at DESC
    """, (pid, branch_id))
    records = c.fetchall()
    conn.close()

    log_audit('branch', branch_id, 'view_patient_record', 'patient', pid)
    return jsonify({'patient': serialize(patient), 'appointments': serialize(appointments), 'records': serialize(records)})


@app.route('/api/branch/patients/<int:pid>/records', methods=['POST'])
@branch_required
def add_patient_record(pid):
    branch_id = get_jwt_identity()
    data = request.json
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT id FROM appointments
        WHERE patient_id = %s AND branch_id = %s AND status IN ('confirmed','completed')
        ORDER BY appointment_date DESC LIMIT 1
    """, (pid, branch_id))
    appt = c.fetchone()
    if not appt:
        conn.close()
        return jsonify({'error': 'No confirmed appointment found for this patient'}), 404

    c.execute("""
        INSERT INTO medical_records (appointment_id, patient_id, branch_id, diagnosis, prescription, notes, vitals)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (appt['id'], pid, branch_id, data.get('diagnosis'), data.get('prescription'),
          data.get('notes'), json.dumps(data.get('vitals')) if data.get('vitals') else None))
    conn.close()
    add_notification('patient', pid, 'Medical Record Added', 'A new medical record has been added to your profile.', 'record')
    log_audit('branch', branch_id, 'add_medical_record', 'patient', pid)
    return jsonify({'message': 'Medical record added'}), 201

# ─────────────────────────────────────────────
# BRANCH — OTHER BRANCHES (read-only)
# ─────────────────────────────────────────────

@app.route('/api/branch/other-branches', methods=['GET'])
@branch_required
def get_other_branches():
    branch_id = get_jwt_identity()
    claims = get_jwt()
    hospital_id = claims.get('hospital_id')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT id, name, address, city, state, phone, is_primary
        FROM branches WHERE hospital_id = %s AND id != %s AND status = 'approved'
    """, (hospital_id, branch_id))
    branches = c.fetchall()
    conn.close()
    return jsonify(branches)


@app.route('/api/branch/other-branches/<int:other_id>/patients', methods=['GET'])
@branch_required
def get_other_branch_patients(other_id):
    branch_id = get_jwt_identity()
    claims = get_jwt()
    hospital_id = claims.get('hospital_id')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id FROM branches WHERE id = %s AND hospital_id = %s", (other_id, hospital_id))
    if not c.fetchone():
        conn.close()
        return jsonify({'error': 'Access denied'}), 403

    search = request.args.get('search', '')
    query = """
        SELECT DISTINCT p.id, p.patient_uid, p.first_name, p.last_name,
               p.phone, p.gender, p.blood_group, MAX(a.appointment_date) as last_visit
        FROM patients p JOIN appointments a ON p.id = a.patient_id
        WHERE a.branch_id = %s
    """
    params = [other_id]
    if search:
        query += " AND (p.first_name LIKE %s OR p.last_name LIKE %s OR p.patient_uid LIKE %s)"
        params.extend([f"%{search}%"] * 3)
    query += " GROUP BY p.id ORDER BY last_visit DESC"
    c.execute(query, params)
    patients = c.fetchall()
    conn.close()
    log_audit('branch', branch_id, 'view_other_branch_patients', 'branch', other_id)
    return jsonify(serialize(patients))


@app.route('/api/branch/other-branches/<int:other_id>/patients/<int:pid>', methods=['GET'])
@branch_required
def get_other_branch_patient_detail(other_id, pid):
    branch_id = get_jwt_identity()
    claims = get_jwt()
    hospital_id = claims.get('hospital_id')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id FROM branches WHERE id = %s AND hospital_id = %s", (other_id, hospital_id))
    if not c.fetchone():
        conn.close()
        return jsonify({'error': 'Access denied'}), 403

    c.execute("""
        SELECT id, patient_uid, first_name, last_name, phone, gender, blood_group, dob,
               emergency_contact_name, emergency_contact_phone
        FROM patients WHERE id = %s
    """, (pid,))
    patient = c.fetchone()
    c.execute("""
        SELECT id, appointment_date, appointment_time, reason, status, confirmation_number
        FROM appointments WHERE patient_id = %s AND branch_id = %s ORDER BY appointment_date DESC
    """, (pid, other_id))
    appointments = c.fetchall()
    c.execute("""
        SELECT mr.id, mr.diagnosis, mr.prescription, mr.notes, mr.created_at, a.appointment_date
        FROM medical_records mr JOIN appointments a ON mr.appointment_id = a.id
        WHERE mr.patient_id = %s AND mr.branch_id = %s ORDER BY mr.created_at DESC
    """, (pid, other_id))
    records = c.fetchall()
    conn.close()
    log_audit('branch', branch_id, 'view_other_branch_patient', 'patient', pid, {'other_branch_id': other_id})
    return jsonify({'patient': serialize(patient), 'appointments': serialize(appointments), 'records': serialize(records)})

# ─────────────────────────────────────────────
# BRANCH — INVITE
# ─────────────────────────────────────────────

@app.route('/api/branch/invite', methods=['POST'])
@branch_required
def invite_branch():
    branch_id = get_jwt_identity()
    claims = get_jwt()
    hospital_id = claims.get('hospital_id')
    email = request.json.get('email')
    if not email:
        return jsonify({'error': 'Email required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id FROM branches WHERE email = %s", (email,))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Email already registered'}), 409

    c.execute("""
        SELECT b.name as branch_name, h.name as hospital_name
        FROM branches b JOIN hospitals h ON b.hospital_id = h.id WHERE b.id = %s
    """, (branch_id,))
    inviter = c.fetchone()

    token = ''.join(random.choices(string.ascii_letters + string.digits, k=48))
    expires_at = datetime.now() + timedelta(days=7)
    c.execute("""
        INSERT INTO branch_invites (hospital_id, inviting_branch_id, invite_token, email, expires_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (hospital_id, branch_id, token, email, expires_at))
    conn.close()

    invite_url = f"http://localhost:5000/auth?mode=branch-invite&token={token}"
    send_email(email, f'Invitation to join {inviter["hospital_name"]} on NEURAX', f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto;padding:32px">
        <h2 style="color:#007AFF">Branch Invitation</h2>
        <p><strong>{inviter['branch_name']}</strong> of <strong>{inviter['hospital_name']}</strong>
        has invited you to register your branch on NEURAX.</p>
        <a href="{invite_url}" style="display:inline-block;background:#007AFF;color:white;
           padding:14px 28px;border-radius:14px;text-decoration:none;font-weight:600;margin:16px 0">
            Register Your Branch
        </a>
        <p style="color:#8E8E93;font-size:12px">This invitation expires in 7 days.</p>
    </div>
    """)
    return jsonify({'message': f'Invitation sent to {email}'})

# ─────────────────────────────────────────────
# BRANCH — CROSS-HOSPITAL ACCESS
# ─────────────────────────────────────────────

@app.route('/api/branch/cross-hospital/request', methods=['POST'])
@branch_required
def request_cross_hospital():
    branch_id = get_jwt_identity()
    claims = get_jwt()
    my_hospital_id = claims.get('hospital_id')
    target_code = request.json.get('hospital_code')
    if not target_code:
        return jsonify({'error': 'Target hospital code required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id, name FROM hospitals WHERE hospital_code = %s AND status = 'approved'", (target_code,))
    target = c.fetchone()
    if not target:
        conn.close()
        return jsonify({'error': 'Hospital not found'}), 404
    if target['id'] == my_hospital_id:
        conn.close()
        return jsonify({'error': 'Cannot request access to your own hospital'}), 400

    c.execute("""
        SELECT id, status FROM cross_hospital_access
        WHERE requesting_hospital_id = %s AND granting_hospital_id = %s
    """, (my_hospital_id, target['id']))
    existing = c.fetchone()
    if existing and existing['status'] in ('granted', 'pending'):
        conn.close()
        return jsonify({'error': f'Request already {existing["status"]}'}), 409

    c.execute("""
        INSERT INTO cross_hospital_access
        (requesting_hospital_id, granting_hospital_id, requesting_branch_id, status)
        VALUES (%s, %s, %s, 'pending')
    """, (my_hospital_id, target['id'], branch_id))

    c.execute("SELECT b.name, h.name as hname FROM branches b JOIN hospitals h ON b.hospital_id=h.id WHERE b.id=%s", (branch_id,))
    requester = c.fetchone()
    c.execute("SELECT b.id, b.email FROM branches b WHERE b.hospital_id = %s AND b.is_primary = TRUE", (target['id'],))
    primary = c.fetchone()
    conn.close()

    if primary:
        add_notification('branch', primary['id'], 'Cross-Hospital Access Request',
                         f"{requester['hname']} is requesting access to your patient records.", 'access_request')
        send_email(primary['email'], 'Cross-Hospital Access Request — NEURAX', f"""
        <div style="font-family:sans-serif;padding:32px">
            <h2 style="color:#FF9500">Access Request</h2>
            <p><strong>{requester['hname']}</strong> is requesting access to your hospital's patient records.</p>
            <p>Login to your dashboard to approve or reject.</p>
        </div>
        """)
    return jsonify({'message': 'Access request sent'}), 201


@app.route('/api/branch/cross-hospital/requests', methods=['GET'])
@branch_required
def get_cross_hospital_requests():
    claims = get_jwt()
    hospital_id = claims.get('hospital_id')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT cha.*, h.name as requesting_hospital_name, h.hospital_code as requesting_code
        FROM cross_hospital_access cha JOIN hospitals h ON cha.requesting_hospital_id = h.id
        WHERE cha.granting_hospital_id = %s ORDER BY cha.requested_at DESC
    """, (hospital_id,))
    incoming = c.fetchall()
    c.execute("""
        SELECT cha.*, h.name as granting_hospital_name, h.hospital_code as granting_code
        FROM cross_hospital_access cha JOIN hospitals h ON cha.granting_hospital_id = h.id
        WHERE cha.requesting_hospital_id = %s ORDER BY cha.requested_at DESC
    """, (hospital_id,))
    outgoing = c.fetchall()
    conn.close()
    return jsonify({'incoming': serialize(incoming), 'outgoing': serialize(outgoing)})


@app.route('/api/branch/cross-hospital/<int:access_id>/approve', methods=['PUT'])
@branch_required
def approve_cross_hospital(access_id):
    branch_id = get_jwt_identity()
    claims = get_jwt()
    hospital_id = claims.get('hospital_id')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM cross_hospital_access WHERE id = %s AND granting_hospital_id = %s",
              (access_id, hospital_id))
    req = c.fetchone()
    if not req:
        conn.close()
        return jsonify({'error': 'Request not found'}), 404
    c.execute("""
        UPDATE cross_hospital_access SET status='granted', granted_at=NOW(), granting_branch_id=%s WHERE id=%s
    """, (branch_id, access_id))
    c.execute("SELECT b.id FROM branches b WHERE b.hospital_id = %s AND b.is_primary = TRUE",
              (req['requesting_hospital_id'],))
    primary = c.fetchone()
    conn.close()
    if primary:
        add_notification('branch', primary['id'], 'Access Granted',
                         'Your cross-hospital access request has been approved.', 'access_granted')
    return jsonify({'message': 'Access granted'})


@app.route('/api/branch/cross-hospital/<int:access_id>/revoke', methods=['PUT'])
@branch_required
def revoke_cross_hospital(access_id):
    claims = get_jwt()
    hospital_id = claims.get('hospital_id')
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE cross_hospital_access SET status='revoked', revoked_at=NOW()
        WHERE id=%s AND granting_hospital_id=%s
    """, (access_id, hospital_id))
    conn.close()
    return jsonify({'message': 'Access revoked'})


@app.route('/api/branch/cross-hospital/accessible', methods=['GET'])
@branch_required
def get_accessible_hospitals():
    claims = get_jwt()
    hospital_id = claims.get('hospital_id')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT cha.id as access_id, h.id, h.name, h.hospital_code, cha.granted_at
        FROM cross_hospital_access cha JOIN hospitals h ON cha.granting_hospital_id = h.id
        WHERE cha.requesting_hospital_id = %s AND cha.status = 'granted'
    """, (hospital_id,))
    hospitals = c.fetchall()
    conn.close()
    return jsonify(serialize(hospitals))


@app.route('/api/branch/cross-hospital/accessible/<int:target_hospital_id>/patients', methods=['GET'])
@branch_required
def get_cross_hospital_patients(target_hospital_id):
    branch_id = get_jwt_identity()
    claims = get_jwt()
    hospital_id = claims.get('hospital_id')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT id FROM cross_hospital_access
        WHERE requesting_hospital_id=%s AND granting_hospital_id=%s AND status='granted'
    """, (hospital_id, target_hospital_id))
    if not c.fetchone():
        conn.close()
        return jsonify({'error': 'Access not granted'}), 403

    search = request.args.get('search', '')
    query = """
        SELECT DISTINCT p.id, p.patient_uid, p.first_name, p.last_name,
               p.phone, p.gender, p.blood_group, b.name as branch_name,
               MAX(a.appointment_date) as last_visit
        FROM patients p JOIN appointments a ON p.id = a.patient_id
        JOIN branches b ON a.branch_id = b.id
        WHERE b.hospital_id = %s
    """
    params = [target_hospital_id]
    if search:
        query += " AND (p.first_name LIKE %s OR p.last_name LIKE %s OR p.patient_uid LIKE %s)"
        params.extend([f"%{search}%"] * 3)
    query += " GROUP BY p.id, b.name ORDER BY last_visit DESC"
    c.execute(query, params)
    patients = c.fetchall()
    conn.close()
    log_audit('branch', branch_id, 'view_cross_hospital_patients', 'hospital', target_hospital_id)
    return jsonify(serialize(patients))

# ─────────────────────────────────────────────
# BRANCH — NOTIFICATIONS
# ─────────────────────────────────────────────

@app.route('/api/branch/notifications', methods=['GET'])
@branch_required
def get_branch_notifications():
    branch_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT * FROM notifications
        WHERE recipient_type='branch' AND recipient_id=%s
        ORDER BY created_at DESC LIMIT 50
    """, (branch_id,))
    notifs = c.fetchall()
    conn.close()
    return jsonify(serialize(notifs))


@app.route('/api/branch/notifications/<int:nid>/read', methods=['PUT'])
@branch_required
def mark_branch_notification_read(nid):
    branch_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE notifications SET is_read=TRUE
        WHERE id=%s AND recipient_type='branch' AND recipient_id=%s
    """, (nid, branch_id))
    conn.close()
    return jsonify({'message': 'Marked as read'})

# ─────────────────────────────────────────────
# ADMIN
# ─────────────────────────────────────────────

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT COUNT(*) as t FROM hospitals"); total_h = c.fetchone()['t']
    c.execute("SELECT COUNT(*) as t FROM hospitals WHERE status='pending'"); pending_h = c.fetchone()['t']
    c.execute("SELECT COUNT(*) as t FROM branches WHERE status='approved'"); total_b = c.fetchone()['t']
    c.execute("SELECT COUNT(*) as t FROM patients"); total_p = c.fetchone()['t']
    c.execute("SELECT COUNT(*) as t FROM appointments"); total_a = c.fetchone()['t']
    conn.close()
    return jsonify({'total_hospitals': total_h, 'pending_hospitals': pending_h,
                    'total_branches': total_b, 'total_patients': total_p, 'total_appointments': total_a})


@app.route('/api/admin/hospitals', methods=['GET'])
@admin_required
def admin_get_hospitals():
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT h.*, COUNT(b.id) as branch_count
        FROM hospitals h LEFT JOIN branches b ON h.id = b.hospital_id
        GROUP BY h.id ORDER BY h.created_at DESC
    """)
    hospitals = c.fetchall()
    conn.close()
    return jsonify(serialize(hospitals))


@app.route('/api/admin/hospitals/<int:hospital_id>/approve', methods=['PUT'])
@admin_required
def admin_approve_hospital(hospital_id):
    action = request.json.get('action')
    if action not in ['approve', 'reject']:
        return jsonify({'error': 'Invalid action'}), 400
    status = 'approved' if action == 'approve' else 'rejected'
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("UPDATE hospitals SET status=%s WHERE id=%s", (status, hospital_id))
    if action == 'approve':
        c.execute("UPDATE branches SET status='approved' WHERE hospital_id=%s AND is_primary=TRUE", (hospital_id,))
    c.execute("""
        SELECT b.email, b.name as branch_name, h.name as hospital_name
        FROM branches b JOIN hospitals h ON b.hospital_id = h.id
        WHERE h.id = %s AND b.is_primary = TRUE
    """, (hospital_id,))
    branch = c.fetchone()
    conn.close()
    if branch:
        if action == 'approve':
            send_email(branch['email'], 'Your hospital has been approved on NEURAX', f"""
            <div style="font-family:sans-serif;padding:32px">
                <h2 style="color:#34C759">Approved!</h2>
                <p><strong>{branch['hospital_name']}</strong> is now live on NEURAX. You can login and start managing appointments.</p>
            </div>""")
        else:
            send_email(branch['email'], 'NEURAX — Registration Update', f"""
            <div style="font-family:sans-serif;padding:32px">
                <h2 style="color:#FF3B30">Registration Update</h2>
                <p>Your registration for <strong>{branch['hospital_name']}</strong> was not approved. Contact support for details.</p>
            </div>""")
    return jsonify({'message': f'Hospital {status}'})


@app.route('/api/admin/audit-logs', methods=['GET'])
@admin_required
def admin_audit_logs():
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 100")
    logs = c.fetchall()
    conn.close()
    result = serialize(logs)
    for l in result:
        if isinstance(l.get('details'), str):
            try: l['details'] = json.loads(l['details'])
            except: pass
    return jsonify(result)

# ─────────────────────────────────────────────
# INVITE VALIDATION
# ─────────────────────────────────────────────

@app.route('/api/auth/invite/validate', methods=['GET'])
def validate_invite():
    token = request.args.get('token')
    if not token:
        return jsonify({'error': 'Token required'}), 400
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT bi.*, h.name as hospital_name, h.hospital_code, b.name as inviting_branch
        FROM branch_invites bi
        JOIN hospitals h ON bi.hospital_id = h.id
        JOIN branches b ON bi.inviting_branch_id = b.id
        WHERE bi.invite_token = %s AND bi.status = 'pending' AND bi.expires_at > NOW()
    """, (token,))
    invite = c.fetchone()
    conn.close()
    if not invite:
        return jsonify({'error': 'Invalid or expired invite'}), 400
    return jsonify({
        'hospital_name': invite['hospital_name'],
        'hospital_code': invite['hospital_code'],
        'inviting_branch': invite['inviting_branch'],
        'email': invite['email']
    })

# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────

if __name__ == '__main__':
    create_tables()
    app.run(debug=True, port=5000)
