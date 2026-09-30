"""
Database management module for PostgreSQL.
Handles PostgreSQL database connections, initializes tables on startup, and provides role-based access control (RBAC) decorators for routes.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config
from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt

class DBConnection:
    """Wrapper around psycopg2 connection to maintain compatibility with cursor(dictionary=True)."""
    def __init__(self, raw_conn):
        self._conn = raw_conn
        self._conn.autocommit = True

    def cursor(self, *args, dictionary=False, **kwargs):
        if dictionary or kwargs.pop('dictionary', False):
            return self._conn.cursor(cursor_factory=RealDictCursor)
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_db():
    raw_conn = psycopg2.connect(Config.get_database_url())
    return DBConnection(raw_conn)

def create_tables():
    conn = get_db()
    c = conn.cursor(dictionary=True)

    # Hospitals
    c.execute("""
        CREATE TABLE IF NOT EXISTS hospitals (
            id                  SERIAL PRIMARY KEY,
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
        );
    """)

    # Patients
    c.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id                      SERIAL PRIMARY KEY,
            patient_uid             VARCHAR(20) UNIQUE NOT NULL,
            first_name              VARCHAR(100) NOT NULL,
            last_name               VARCHAR(100) NOT NULL,
            email                   VARCHAR(150) UNIQUE NOT NULL,
            password_hash           VARCHAR(255) NOT NULL,
            phone                   VARCHAR(20),
            dob                     DATE,
            gender                  VARCHAR(20),
            blood_group             VARCHAR(5),
            emergency_contact_name  VARCHAR(100),
            emergency_contact_phone VARCHAR(20),
            address                 TEXT,
            created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Doctors
    c.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id               SERIAL PRIMARY KEY,
            name             VARCHAR(150) NOT NULL,
            specialization   VARCHAR(100) NOT NULL,
            qualification    VARCHAR(200),
            experience_years INT DEFAULT 0,
            is_active        BOOLEAN DEFAULT TRUE,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Seed doctors if table is empty
    c.execute("SELECT COUNT(*) as cnt FROM doctors")
    row = c.fetchone()
    if row['cnt'] == 0:
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
            id                  SERIAL PRIMARY KEY,
            patient_id          INT NOT NULL REFERENCES patients(id),
            hospital_id         INT NOT NULL REFERENCES hospitals(id),
            doctor_id           INT REFERENCES doctors(id),
            appointment_date    DATE NOT NULL,
            appointment_time    VARCHAR(10) NOT NULL,
            reason              TEXT,
            status              VARCHAR(20) DEFAULT 'pending',
            confirmation_number VARCHAR(20) UNIQUE NOT NULL,
            notes               TEXT,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Medical Records
    c.execute("""
        CREATE TABLE IF NOT EXISTS medical_records (
            id             SERIAL PRIMARY KEY,
            appointment_id INT NOT NULL REFERENCES appointments(id),
            hospital_id    INT NOT NULL REFERENCES hospitals(id),
            patient_id     INT NOT NULL REFERENCES patients(id),
            diagnosis      TEXT,
            prescription   TEXT,
            notes          TEXT,
            vitals         JSON,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Cross Hospital Access
    c.execute("""
        CREATE TABLE IF NOT EXISTS cross_hospital_access (
            id                    SERIAL PRIMARY KEY,
            requesting_hospital_id INT NOT NULL REFERENCES hospitals(id),
            granting_hospital_id   INT NOT NULL REFERENCES hospitals(id),
            status                 VARCHAR(20) DEFAULT 'pending',
            requested_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            granted_at             TIMESTAMP NULL,
            revoked_at             TIMESTAMP NULL
        );
    """)

    # Notifications
    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id             SERIAL PRIMARY KEY,
            recipient_type VARCHAR(20) NOT NULL,
            recipient_id   INT NOT NULL,
            title          VARCHAR(200) NOT NULL,
            message        TEXT NOT NULL,
            type           VARCHAR(50),
            is_read        BOOLEAN DEFAULT FALSE,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Password Reset OTPs
    c.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_otps (
            id         SERIAL PRIMARY KEY,
            email      VARCHAR(150) NOT NULL,
            user_type  VARCHAR(20) NOT NULL,
            otp_hash   VARCHAR(64) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used       BOOLEAN DEFAULT FALSE
        );
    """)

    # Conversations
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id         SERIAL PRIMARY KEY,
            patient_id INT NOT NULL REFERENCES patients(id),
            session_id VARCHAR(64) NOT NULL,
            role       VARCHAR(20) NOT NULL,
            message    TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Chat Sessions
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id VARCHAR(64) PRIMARY KEY,
            patient_id INT NOT NULL REFERENCES patients(id),
            title      VARCHAR(120) NOT NULL DEFAULT 'Chat Session',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Audit Logs
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id          SERIAL PRIMARY KEY,
            actor_type  VARCHAR(20) NOT NULL,
            actor_id    INT NOT NULL,
            action      VARCHAR(100) NOT NULL,
            target_type VARCHAR(50),
            target_id   INT,
            details     JSON,
            ip_address  VARCHAR(45),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    c.close()
    conn.close()
    print("[NEURAX] PostgreSQL database tables ready.")

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
