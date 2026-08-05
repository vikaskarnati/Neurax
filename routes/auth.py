"""
Authentication routes blueprint.
Handles user registration, login, JWT token issuance, and password reset flows for all user roles.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

from config import Config
from database import get_db
from utils.helpers import generate_patient_uid, generate_hospital_code, generate_otp, hash_otp, send_email

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/auth/patient/register', methods=['POST'])
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


@auth_bp.route('/api/auth/patient/login', methods=['POST'])
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
        'token':       token,
        'patient_uid': patient['patient_uid'],
        'first_name':  patient['first_name'],
        'last_name':   patient['last_name']
    })


@auth_bp.route('/api/auth/hospital/register', methods=['POST'])
def hospital_register():
    data = request.json
    required = ['hospital_name', 'hospital_type', 'registration_number',
                'address', 'city', 'state', 'phone', 'email', 'password']
    if not all(data.get(f) for f in required):
        return jsonify({'error': 'All fields are required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id FROM hospitals WHERE email = %s", (data['email'],))
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
        INSERT INTO hospitals (name, type, registration_number, hospital_code,
                               address, city, state, phone, email, password_hash)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (data['hospital_name'], data['hospital_type'], data['registration_number'],
          hospital_code, data['address'], data['city'], data['state'],
          data['phone'], data['email'], generate_password_hash(data['password'])))
    conn.close()

    send_email(Config.ADMIN_EMAIL, f'New Hospital Registration: {data["hospital_name"]}', f"""
    <div style="font-family:sans-serif;padding:24px">
        <h2>New Hospital Registration</h2>
        <p><strong>Hospital:</strong> {data['hospital_name']} ({data['hospital_type']})</p>
        <p><strong>Reg No:</strong> {data['registration_number']}</p>
        <p><strong>Location:</strong> {data['city']}, {data['state']}</p>
        <p><strong>Contact:</strong> {data['email']} | {data['phone']}</p>
        <p>Login to the admin panel to approve or reject.</p>
    </div>
    """)

    return jsonify({
        'message':       'Registration submitted. Awaiting admin approval.',
        'hospital_code': hospital_code
    }), 201


@auth_bp.route('/api/auth/hospital/login', methods=['POST'])
def hospital_login():
    data = request.json
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM hospitals WHERE email = %s", (data['email'],))
    hospital = c.fetchone()
    conn.close()

    if not hospital or not check_password_hash(hospital['password_hash'], data['password']):
        return jsonify({'error': 'Invalid email or password'}), 401

    token = create_access_token(
        identity=str(hospital['id']),
        additional_claims={'role': 'hospital'}
    )
    return jsonify({
        'token':         token,
        'hospital_name': hospital['name'],
        'hospital_code': hospital['hospital_code'],
        'city':          hospital['city']
    })


@auth_bp.route('/api/auth/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    if data.get('email') != Config.ADMIN_EMAIL or data.get('password') != Config.ADMIN_PASSWORD:
        return jsonify({'error': 'Invalid credentials'}), 401
    token = create_access_token(identity='admin', additional_claims={'role': 'admin'})
    return jsonify({'token': token})


@auth_bp.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    data     = request.json
    email    = data.get('email')
    user_type = data.get('user_type')
    if not email or not user_type:
        return jsonify({'error': 'Email and user_type required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    if user_type == 'patient':
        c.execute("SELECT id FROM patients WHERE email = %s", (email,))
    else:
        c.execute("SELECT id FROM hospitals WHERE email = %s", (email,))
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


@auth_bp.route('/api/auth/reset-password', methods=['POST'])
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
        c.execute("UPDATE patients  SET password_hash = %s WHERE email = %s", (new_hash, email))
    else:
        c.execute("UPDATE hospitals SET password_hash = %s WHERE email = %s", (new_hash, email))
    c.execute("UPDATE password_reset_otps SET used = TRUE WHERE id = %s", (record['id'],))
    conn.close()
    return jsonify({'message': 'Password reset successfully'})
