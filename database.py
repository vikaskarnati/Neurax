"""
Database management module.
Handles MySQL database connections, initializes tables on startup, and provides role-based access control (RBAC) decorators for routes.
"""
import mysql.connector
from config import Config
from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt

def get_db():
    return mysql.connector.connect(**Config.DB_CONFIG)

def create_tables():
    conn = get_db()
    c = conn.cursor(dictionary=True)

    # Hospitals
    c.execute("""
        CREATE TABLE IF NOT EXISTS hospitals (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            name                VARCHAR(200) NOT NULL,
            type                VARCHAR(100),
            registration_number VARCHAR(100),
            hospital_code       VARCHAR(20) UNIQUE NOT NULL,
            address             TEXT,
            city                VARCHAR(100),
            state               VARCHAR(100),
            phone               VARCHAR(20),
            email               VARCHAR(150) UNIQUE NOT NULL,
            password_hash       VARCHAR(255) NOT NULL,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Patients
    c.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id                      INT AUTO_INCREMENT PRIMARY KEY,
            patient_uid             VARCHAR(20) UNIQUE NOT NULL,
            first_name              VARCHAR(100) NOT NULL,
            last_name               VARCHAR(100) NOT NULL,
            email                   VARCHAR(150) UNIQUE NOT NULL,
            password_hash           VARCHAR(255) NOT NULL,
            phone                   VARCHAR(20),
            dob                     DATE,
            gender                  ENUM('male','female','other'),
            blood_group             VARCHAR(5),
            emergency_contact_name  VARCHAR(100),
            emergency_contact_phone VARCHAR(20),
            address                 TEXT,
            created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Doctors
    c.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id               INT AUTO_INCREMENT PRIMARY KEY,
            name             VARCHAR(150) NOT NULL,
            specialization   VARCHAR(100) NOT NULL,
            qualification    VARCHAR(200),
            experience_years INT DEFAULT 0,
            is_active        BOOLEAN DEFAULT TRUE,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed doctors if table is empty
    c.execute("SELECT COUNT(*) as cnt FROM doctors")
    if c.fetchone()['cnt'] == 0:
        doctors_seed = [
            ('Dr. Arjun Sharma',       'General Medicine',   'MBBS, MD',          12),
            ('Dr. Priya Menon',        'General Medicine',   'MBBS, DNB',          8),
            ('Dr. Rajesh Gupta',       'Cardiology',         'MBBS, DM Cardiology',18),
            ('Dr. Sunita Rao',         'Cardiology',         'MBBS, MD, DM',       15),
            ('Dr. Vikram Nair',        'Orthopedics',        'MBBS, MS Ortho',     14),
            ('Dr. Kavitha Iyer',       'Orthopedics',        'MBBS, DNB Ortho',    10),
            ('Dr. Anil Khanna',        'Dermatology',        'MBBS, MD Derma',      9),
            ('Dr. Meera Pillai',       'Dermatology',        'MBBS, DVD',           7),
            ('Dr. Suresh Patel',       'Neurology',          'MBBS, DM Neurology', 20),
            ('Dr. Deepa Krishnan',     'Neurology',          'MBBS, MD, DM',       13),
            ('Dr. Ravi Verma',         'Pediatrics',         'MBBS, MD Pediatrics',11),
            ('Dr. Ananya Bose',        'Gynecology',         'MBBS, MS OBG',       16),
            ('Dr. Sanjay Joshi',       'ENT',                'MBBS, MS ENT',        9),
            ('Dr. Rekha Nambiar',      'Ophthalmology',      'MBBS, MS Ophtha',    12),
            ('Dr. Karthik Reddy',      'Psychiatry',         'MBBS, MD Psychiatry', 8),
            ('Dr. Leela Subramaniam',  'Gastroenterology',   'MBBS, DM Gastro',    17),
            ('Dr. Mohan Das',          'Pulmonology',        'MBBS, MD, DM Pulmo', 14),
            ('Dr. Divya Chandran',     'Endocrinology',      'MBBS, DM Endo',      10),
            ('Dr. Prakash Mehta',      'Urology',            'MBBS, MS, MCh Uro',  19),
            ('Dr. Nalini Seshadri',    'Oncology',           'MBBS, MD, DM Onco',  22),
        ]
        c.executemany(
            "INSERT INTO doctors (name, specialization, qualification, experience_years) VALUES (%s,%s,%s,%s)",
            doctors_seed
        )

    # Appointments
    c.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            patient_id          INT NOT NULL,
            hospital_id         INT NOT NULL,
            doctor_id           INT,
            appointment_date    DATE NOT NULL,
            appointment_time    VARCHAR(10) NOT NULL,
            reason              TEXT,
            status              ENUM('pending','confirmed','completed','cancelled') DEFAULT 'pending',
            confirmation_number VARCHAR(20) UNIQUE NOT NULL,
            notes               TEXT,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id)  REFERENCES patients(id),
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id),
            FOREIGN KEY (doctor_id)   REFERENCES doctors(id)
        )
    """)
    try:
        c.execute("ALTER TABLE appointments ADD COLUMN doctor_id INT, ADD FOREIGN KEY (doctor_id) REFERENCES doctors(id)")
    except Exception:
        pass

    # Medical Records
    c.execute("""
        CREATE TABLE IF NOT EXISTS medical_records (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            appointment_id INT NOT NULL,
            hospital_id    INT NOT NULL,
            patient_id     INT NOT NULL,
            diagnosis      TEXT,
            prescription   TEXT,
            notes          TEXT,
            vitals         JSON,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (appointment_id) REFERENCES appointments(id),
            FOREIGN KEY (patient_id)     REFERENCES patients(id),
            FOREIGN KEY (hospital_id)    REFERENCES hospitals(id)
        )
    """)

    # Cross Hospital Access
    c.execute("""
        CREATE TABLE IF NOT EXISTS cross_hospital_access (
            id                    INT AUTO_INCREMENT PRIMARY KEY,
            requesting_hospital_id INT NOT NULL,
            granting_hospital_id   INT NOT NULL,
            status                 ENUM('pending','granted','revoked') DEFAULT 'pending',
            requested_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            granted_at             TIMESTAMP NULL,
            revoked_at             TIMESTAMP NULL,
            FOREIGN KEY (requesting_hospital_id) REFERENCES hospitals(id),
            FOREIGN KEY (granting_hospital_id)   REFERENCES hospitals(id)
        )
    """)

    # Notifications
    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            recipient_type ENUM('patient','hospital','admin') NOT NULL,
            recipient_id   INT NOT NULL,
            title          VARCHAR(200) NOT NULL,
            message        TEXT NOT NULL,
            type           VARCHAR(50),
            is_read        BOOLEAN DEFAULT FALSE,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Password Reset OTPs
    c.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_otps (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            email      VARCHAR(150) NOT NULL,
            user_type  ENUM('patient','hospital') NOT NULL,
            otp_hash   VARCHAR(64) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used       BOOLEAN DEFAULT FALSE
        )
    """)

    # Conversations
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            patient_id INT NOT NULL,
            session_id VARCHAR(64) NOT NULL,
            role       ENUM('user','assistant') NOT NULL,
            message    TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    # Chat Sessions
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id VARCHAR(64) PRIMARY KEY,
            patient_id INT NOT NULL,
            title      VARCHAR(120) NOT NULL DEFAULT 'Chat Session',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    # Audit Logs
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            actor_type  ENUM('patient','hospital','admin') NOT NULL,
            actor_id    INT NOT NULL,
            action      VARCHAR(100) NOT NULL,
            target_type VARCHAR(50),
            target_id   INT,
            details     JSON,
            ip_address  VARCHAR(45),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.close()
    print("Database tables ready.")

# RBAC Decorators
def hospital_required(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        claims = get_jwt()
        if claims.get('role') != 'hospital':
            return jsonify({'error': 'Hospital access required'}), 403
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
