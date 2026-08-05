"""
Utility helper functions.
Contains reusable functions for generating UIDs, OTPs, handling email dispatch, logging, and formatting responses.
"""
import random
import string
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from config import Config
from database import get_db

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
        msg['From']    = Config.MAIL_EMAIL
        msg['To']      = to_email
        msg.attach(MIMEText(html_body, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(Config.MAIL_EMAIL, Config.MAIL_PASSWORD)
            server.sendmail(Config.MAIL_EMAIL, to_email, msg.as_string())
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
