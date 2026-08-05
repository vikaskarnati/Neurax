"""
Hospital routes blueprint.
Manages hospital-specific endpoints such as dashboard statistics, patient records management, and cross-hospital access requests.
"""
import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from database import get_db, hospital_required
from utils.helpers import serialize, log_audit, add_notification, send_email

hospital_bp = Blueprint('hospital', __name__)

@hospital_bp.route('/api/hospital/profile', methods=['GET'])
@hospital_required
def get_hospital_profile():
    hospital_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT id, name, type, registration_number, hospital_code,
               address, city, state, phone, email, created_at
        FROM hospitals WHERE id = %s
    """, (hospital_id,))
    hospital = c.fetchone()
    conn.close()
    return jsonify(serialize(hospital))

@hospital_bp.route('/api/hospital/dashboard/stats', methods=['GET'])
@hospital_required
def get_hospital_stats():
    hospital_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT COUNT(*) as total FROM appointments WHERE hospital_id = %s", (hospital_id,))
    total = c.fetchone()['total']
    c.execute("SELECT COUNT(*) as total FROM appointments WHERE hospital_id = %s AND status='pending'", (hospital_id,))
    pending = c.fetchone()['total']
    c.execute("SELECT COUNT(*) as total FROM appointments WHERE hospital_id = %s AND appointment_date=CURDATE()", (hospital_id,))
    today = c.fetchone()['total']
    c.execute("SELECT COUNT(DISTINCT patient_id) as total FROM appointments WHERE hospital_id = %s", (hospital_id,))
    patients = c.fetchone()['total']
    c.execute("""
        SELECT DATE(appointment_date) as date, COUNT(*) as count
        FROM appointments WHERE hospital_id = %s
        AND appointment_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        GROUP BY DATE(appointment_date) ORDER BY date
    """, (hospital_id,))
    weekly = c.fetchall()
    conn.close()

    return jsonify({
        'total_appointments':   total,
        'pending_appointments': pending,
        'today_appointments':   today,
        'unique_patients':      patients,
        'weekly_chart':         serialize(weekly)
    })

@hospital_bp.route('/api/hospital/appointments', methods=['GET'])
@hospital_required
def get_hospital_appointments():
    hospital_id = get_jwt_identity()
    status = request.args.get('status', '')
    date   = request.args.get('date', '')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    query = """
        SELECT a.*,
               CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
               p.patient_uid, p.phone AS patient_phone,
               p.blood_group, p.gender, p.dob,
               a.appointment_date AS date,
               a.appointment_time AS time,
               d.name AS doctor_name, d.specialization AS doctor_specialization
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        LEFT JOIN doctors d ON a.doctor_id = d.id
        WHERE a.hospital_id = %s
    """
    params = [hospital_id]
    if status:
        query += " AND a.status = %s"; params.append(status)
    if date:
        query += " AND a.appointment_date = %s"; params.append(date)
    query += " ORDER BY a.appointment_date DESC, a.appointment_time DESC"
    c.execute(query, params)
    appts = c.fetchall()
    conn.close()
    return jsonify(serialize(appts))

@hospital_bp.route('/api/hospital/appointments/<int:appt_id>/status', methods=['PUT'])
@hospital_required
def update_appointment_status(appt_id):
    hospital_id = get_jwt_identity()
    data       = request.json
    new_status = data.get('status')
    if new_status not in ['confirmed', 'completed', 'cancelled']:
        return jsonify({'error': 'Invalid status'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM appointments WHERE id = %s AND hospital_id = %s", (appt_id, hospital_id))
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

@hospital_bp.route('/api/hospital/patients', methods=['GET'])
@hospital_required
def get_hospital_patients():
    search = request.args.get('search', '')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    query = """
        SELECT p.id,
               p.patient_uid AS uid,
               CONCAT(p.first_name, ' ', p.last_name) AS name,
               p.phone, p.gender, p.blood_group, p.dob,
               MAX(a.appointment_date) as last_visit
        FROM patients p
        LEFT JOIN appointments a ON p.id = a.patient_id
    """
    params = []
    if search:
        terms = [t for t in search.split() if t]
        conditions = []
        for term in terms:
            t = f"%{term}%"
            conditions.append(
                "(p.first_name LIKE %s OR p.last_name LIKE %s "
                "OR CONCAT(p.first_name,' ',p.last_name) LIKE %s "
                "OR p.patient_uid LIKE %s OR p.phone LIKE %s)"
            )
            params.extend([t, t, t, t, t])
        query += " WHERE " + " AND ".join(conditions)
    query += " GROUP BY p.id ORDER BY last_visit DESC, p.created_at DESC"
    c.execute(query, params)
    patients = c.fetchall()
    conn.close()
    return jsonify(serialize(patients))

@hospital_bp.route('/api/hospital/patients/<int:pid>/records', methods=['GET'])
@hospital_required
def get_patient_records_hospital(pid):
    hospital_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT id,
               patient_uid AS uid,
               CONCAT(first_name, ' ', last_name) AS name,
               email, phone, dob, gender, blood_group,
               emergency_contact_name, emergency_contact_phone
        FROM patients WHERE id = %s
    """, (pid,))
    patient = c.fetchone()
    if not patient:
        conn.close()
        return jsonify({'error': 'Patient not found'}), 404

    c.execute("""
        SELECT a.*, h.name AS hospital_name,
               a.appointment_date AS date, a.appointment_time AS time
        FROM appointments a
        JOIN hospitals h ON a.hospital_id = h.id
        WHERE a.patient_id = %s ORDER BY a.appointment_date DESC
    """, (pid,))
    appointments = c.fetchall()

    c.execute("""
        SELECT mr.*, h.name AS hospital_name, a.appointment_date, a.reason
        FROM medical_records mr
        JOIN appointments a ON mr.appointment_id = a.id
        JOIN hospitals h ON mr.hospital_id = h.id
        WHERE mr.patient_id = %s ORDER BY mr.created_at DESC
    """, (pid,))
    records = c.fetchall()
    conn.close()

    log_audit('hospital', hospital_id, 'view_patient_record', 'patient', pid)
    return jsonify({'patient': serialize(patient), 'appointments': serialize(appointments), 'records': serialize(records)})

@hospital_bp.route('/api/hospital/patients/<int:pid>/records', methods=['POST'])
@hospital_required
def add_patient_record(pid):
    hospital_id = get_jwt_identity()
    data = request.json
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT id FROM appointments
        WHERE patient_id = %s AND hospital_id = %s AND status IN ('confirmed','completed')
        ORDER BY appointment_date DESC LIMIT 1
    """, (pid, hospital_id))
    appt = c.fetchone()
    if not appt:
        conn.close()
        return jsonify({'error': 'No confirmed appointment found for this patient'}), 404

    c.execute("""
        INSERT INTO medical_records (appointment_id, patient_id, hospital_id, diagnosis, prescription, notes, vitals)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (appt['id'], pid, hospital_id, data.get('diagnosis'), data.get('prescription'),
          data.get('notes'), json.dumps(data.get('vitals')) if data.get('vitals') else None))
    conn.close()
    add_notification('patient', pid, 'Medical Record Added', 'A new medical record has been added to your profile.', 'record')
    log_audit('hospital', hospital_id, 'add_medical_record', 'patient', pid)
    return jsonify({'message': 'Medical record added'}), 201

@hospital_bp.route('/api/hospital/cross-hospital/request', methods=['POST'])
@hospital_required
def request_cross_hospital():
    my_hospital_id = get_jwt_identity()
    target_code    = request.json.get('hospital_code')
    if not target_code:
        return jsonify({'error': 'Target hospital code required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id, name FROM hospitals WHERE hospital_code = %s", (target_code,))
    target = c.fetchone()
    if not target:
        conn.close()
        return jsonify({'error': 'Hospital not found'}), 404
    if str(target['id']) == str(my_hospital_id):
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
        INSERT INTO cross_hospital_access (requesting_hospital_id, granting_hospital_id, status)
        VALUES (%s, %s, 'pending')
    """, (my_hospital_id, target['id']))

    c.execute("SELECT name FROM hospitals WHERE id = %s", (my_hospital_id,))
    requester = c.fetchone()
    c.execute("SELECT email FROM hospitals WHERE id = %s", (target['id'],))
    target_contact = c.fetchone()
    conn.close()

    add_notification('hospital', target['id'], 'Cross-Hospital Access Request',
                     f"{requester['name']} is requesting access to your patient records.", 'access_request')
    if target_contact:
        send_email(target_contact['email'], 'Cross-Hospital Access Request — NEURAX', f"""
        <div style="font-family:sans-serif;padding:32px">
            <h2 style="color:#FF9500">Access Request</h2>
            <p><strong>{requester['name']}</strong> is requesting access to your hospital's patient records.</p>
            <p>Login to your dashboard to approve or reject.</p>
        </div>
        """)
    return jsonify({'message': 'Access request sent'}), 201

@hospital_bp.route('/api/hospital/cross-hospital/requests', methods=['GET'])
@hospital_required
def get_cross_hospital_requests():
    hospital_id = get_jwt_identity()
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

@hospital_bp.route('/api/hospital/cross-hospital/<int:access_id>/approve', methods=['PUT'])
@hospital_required
def approve_cross_hospital(access_id):
    hospital_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM cross_hospital_access WHERE id = %s AND granting_hospital_id = %s",
              (access_id, hospital_id))
    req = c.fetchone()
    if not req:
        conn.close()
        return jsonify({'error': 'Request not found'}), 404
    c.execute("""
        UPDATE cross_hospital_access SET status='granted', granted_at=NOW() WHERE id=%s
    """, (access_id,))
    conn.close()
    add_notification('hospital', req['requesting_hospital_id'], 'Access Granted',
                     'Your cross-hospital access request has been approved.', 'access_granted')
    return jsonify({'message': 'Access granted'})

@hospital_bp.route('/api/hospital/cross-hospital/<int:access_id>/revoke', methods=['PUT'])
@hospital_required
def revoke_cross_hospital(access_id):
    hospital_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE cross_hospital_access SET status='revoked', revoked_at=NOW()
        WHERE id=%s AND granting_hospital_id=%s
    """, (access_id, hospital_id))
    conn.close()
    return jsonify({'message': 'Access revoked'})

@hospital_bp.route('/api/hospital/cross-hospital/accessible', methods=['GET'])
@hospital_required
def get_accessible_hospitals():
    hospital_id = get_jwt_identity()
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

@hospital_bp.route('/api/hospital/cross-hospital/accessible/<int:target_hospital_id>/patients', methods=['GET'])
@hospital_required
def get_cross_hospital_patients(target_hospital_id):
    hospital_id = get_jwt_identity()
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
               p.phone, p.gender, p.blood_group,
               MAX(a.appointment_date) as last_visit
        FROM patients p JOIN appointments a ON p.id = a.patient_id
        WHERE a.hospital_id = %s
    """
    params = [target_hospital_id]
    if search:
        query += " AND (p.first_name LIKE %s OR p.last_name LIKE %s OR p.patient_uid LIKE %s)"
        params.extend([f"%{search}%"] * 3)
    query += " GROUP BY p.id ORDER BY last_visit DESC"
    c.execute(query, params)
    patients = c.fetchall()
    conn.close()
    log_audit('hospital', hospital_id, 'view_cross_hospital_patients', 'hospital', target_hospital_id)
    return jsonify(serialize(patients))

@hospital_bp.route('/api/hospital/notifications', methods=['GET'])
@hospital_required
def get_hospital_notifications():
    hospital_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT * FROM notifications
        WHERE recipient_type='hospital' AND recipient_id=%s
        ORDER BY created_at DESC LIMIT 50
    """, (hospital_id,))
    notifs = c.fetchall()
    conn.close()
    return jsonify(serialize(notifs))

@hospital_bp.route('/api/hospital/notifications/<int:nid>/read', methods=['PUT'])
@hospital_required
def mark_hospital_notification_read(nid):
    hospital_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE notifications SET is_read=TRUE
        WHERE id=%s AND recipient_type='hospital' AND recipient_id=%s
    """, (nid, hospital_id))
    conn.close()
    return jsonify({'message': 'Marked as read'})

@hospital_bp.route('/api/hospital/notifications/<int:nid>', methods=['DELETE'])
@hospital_required
def delete_hospital_notification(nid):
    hospital_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM notifications WHERE id=%s AND recipient_type='hospital' AND recipient_id=%s",
              (nid, hospital_id))
    conn.close()
    return jsonify({'message': 'Deleted'})

@hospital_bp.route('/api/hospital/notifications', methods=['DELETE'])
@hospital_required
def delete_all_hospital_notifications():
    hospital_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM notifications WHERE recipient_type='hospital' AND recipient_id=%s", (hospital_id,))
    conn.close()
    return jsonify({'message': 'All notifications deleted'})
