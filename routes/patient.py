"""
Patient routes blueprint.
Contains endpoints for patient profiles, medical history, appointment booking, PDF card generation, and the Groq-powered AI chatbot.
"""
import json
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity, decode_token
from groq import Groq

from config import Config
from database import get_db, patient_required
from utils.helpers import serialize, generate_confirmation_number, add_notification, send_email
from services.pdf_generator import generate_patient_card_pdf

patient_bp = Blueprint('patient', __name__)

VALID_SPECIALIZATIONS = [
    'General Medicine', 'Cardiology', 'Orthopedics', 'Dermatology',
    'Neurology', 'Pediatrics', 'Gynecology', 'ENT',
    'Ophthalmology', 'Psychiatry', 'Gastroenterology', 'Pulmonology',
    'Endocrinology', 'Urology', 'Oncology',
]

@patient_bp.route('/api/patient/profile', methods=['GET'])
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

@patient_bp.route('/api/patient/profile', methods=['PUT'])
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

@patient_bp.route('/api/patient/card', methods=['GET'])
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
        SELECT a.*, h.name as hospital_name, h.city, h.phone as hospital_phone
        FROM appointments a
        JOIN hospitals h ON a.hospital_id = h.id
        WHERE a.patient_id = %s ORDER BY a.created_at DESC LIMIT 5
    """, (patient_id,))
    recent_appointments = c.fetchall()
    c.execute("""
        SELECT mr.*, h.name as hospital_name
        FROM medical_records mr
        JOIN hospitals h ON mr.hospital_id = h.id
        WHERE mr.patient_id = %s ORDER BY mr.created_at DESC LIMIT 3
    """, (patient_id,))
    recent_records = c.fetchall()
    conn.close()
    return jsonify({
        'patient':              serialize(patient),
        'recent_appointments':  serialize(recent_appointments),
        'recent_records':       serialize(recent_records)
    })

@patient_bp.route('/api/patient/card/pdf', methods=['GET'])
def download_patient_card_pdf():
    token = request.args.get('token', '')
    if not token:
        return jsonify({'error': 'Missing token'}), 401
    try:
        decoded = decode_token(token)
        if decoded.get('role') != 'patient':
            return jsonify({'error': 'Forbidden'}), 403
        patient_id = decoded['sub']
    except Exception:
        return jsonify({'error': 'Invalid or expired token'}), 401
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
    patient = c.fetchone()
    c.execute("""
        SELECT a.*, h.name as hospital_name, h.city
        FROM appointments a
        JOIN hospitals h ON a.hospital_id = h.id
        WHERE a.patient_id = %s ORDER BY a.appointment_date DESC LIMIT 10
    """, (patient_id,))
    appointments = c.fetchall()
    c.execute("""
        SELECT mr.diagnosis, mr.prescription, mr.notes, mr.vitals,
               mr.created_at, h.name as hospital_name,
               a.appointment_date, a.reason
        FROM medical_records mr
        JOIN appointments a ON mr.appointment_id = a.id
        JOIN hospitals h ON mr.hospital_id = h.id
        WHERE mr.patient_id = %s ORDER BY mr.created_at DESC
    """, (patient_id,))
    medical_records = c.fetchall()
    conn.close()

    return generate_patient_card_pdf(patient, appointments, medical_records)

@patient_bp.route('/api/patient/appointments', methods=['GET'])
@patient_required
def get_patient_appointments():
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT a.*, h.name as hospital_name, h.city, h.phone as hospital_phone,
               d.name as doctor_name, d.specialization as doctor_specialization
        FROM appointments a
        JOIN hospitals h ON a.hospital_id = h.id
        LEFT JOIN doctors d ON a.doctor_id = d.id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """, (patient_id,))
    appts = c.fetchall()
    conn.close()
    return jsonify(serialize(appts))

@patient_bp.route('/api/classify-symptom', methods=['POST'])
@patient_required
def classify_symptom():
    data = request.json
    reason = (data.get('reason') or '').strip()
    if not reason:
        return jsonify({'error': 'Reason is required'}), 400
    try:
        valid_list = ', '.join(VALID_SPECIALIZATIONS)
        client = Groq(api_key=Config.GROQ_API_KEY)
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[
                {'role': 'system', 'content': (
                    f'You are a medical triage assistant. Given a patient symptom description, '
                    f'respond with ONLY the single most relevant medical specialization from this list: {valid_list}. '
                    f'Reply with exactly one item from the list, nothing else.'
                )},
                {'role': 'user', 'content': reason[:400]}
            ],
            max_tokens=15,
            temperature=0.1
        )
        raw = resp.choices[0].message.content.strip()
        matched = next((s for s in VALID_SPECIALIZATIONS if s.lower() == raw.lower()), None)
        specialization = matched or 'General Medicine'
    except Exception:
        specialization = 'General Medicine'
    return jsonify({'specialization': specialization})

@patient_bp.route('/api/patient/appointments/book', methods=['POST'])
@patient_required
def book_appointment():
    patient_id = get_jwt_identity()
    data = request.json
    required = ['hospital_id', 'appointment_date', 'appointment_time', 'reason']
    if not all(data.get(f) for f in required):
        return jsonify({'error': 'All fields required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT id, name FROM hospitals WHERE id = %s", (data['hospital_id'],))
    hospital = c.fetchone()
    if not hospital:
        conn.close()
        return jsonify({'error': 'Hospital not found'}), 404

    conf = generate_confirmation_number()
    while True:
        c.execute("SELECT id FROM appointments WHERE confirmation_number = %s", (conf,))
        if not c.fetchone():
            break
        conf = generate_confirmation_number()

    doctor_id = data.get('doctor_id') or None

    c.execute("""
        INSERT INTO appointments (patient_id, hospital_id, doctor_id, appointment_date, appointment_time, reason, confirmation_number)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (patient_id, data['hospital_id'], doctor_id, data['appointment_date'],
          data['appointment_time'], data['reason'], conf))

    c.execute("SELECT first_name, last_name, email FROM patients WHERE id = %s", (patient_id,))
    patient = c.fetchone()
    conn.close()

    add_notification('patient', patient_id, 'Appointment Booked',
                     f"Appointment at {hospital['name']} on {data['appointment_date']} submitted.", 'appointment')
    add_notification('hospital', data['hospital_id'], 'New Appointment',
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
                    <td style="padding:4px 0">{hospital['name']}</td></tr>
                <tr><td style="color:#8E8E93;padding:4px 0;font-size:13px">Date &amp; Time</td>
                    <td style="padding:4px 0">{data['appointment_date']} at {data['appointment_time']}</td></tr>
                <tr><td style="color:#8E8E93;padding:4px 0;font-size:13px">Reason</td>
                    <td style="padding:4px 0">{data['reason']}</td></tr>
            </table>
        </div>
        <p style="color:#8E8E93;font-size:12px">NEURAX Health Platform</p>
    </div>
    """)
    return jsonify({'message': 'Appointment booked', 'confirmation_number': conf}), 201

@patient_bp.route('/api/patient/hospitals', methods=['GET'])
@patient_required
def get_hospitals():
    search = request.args.get('search', '')
    conn = get_db()
    c = conn.cursor(dictionary=True)
    query = "SELECT id, name, type, hospital_code, city, state FROM hospitals WHERE 1=1"
    params = []
    if search:
        query += " AND (name LIKE %s OR city LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY name"
    c.execute(query, params)
    hospitals = c.fetchall()
    conn.close()
    return jsonify(hospitals)

@patient_bp.route('/api/patient/medical-history', methods=['GET'])
@patient_required
def get_patient_medical_history():
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT mr.*, a.appointment_date, a.appointment_time, a.reason,
               h.name as hospital_name
        FROM medical_records mr
        JOIN appointments a ON mr.appointment_id = a.id
        JOIN hospitals h ON mr.hospital_id = h.id
        WHERE mr.patient_id = %s ORDER BY mr.created_at DESC
    """, (patient_id,))
    records = c.fetchall()
    conn.close()
    return jsonify(serialize(records))

@patient_bp.route('/api/patient/notifications', methods=['GET'])
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

@patient_bp.route('/api/patient/notifications/<int:notif_id>/read', methods=['PUT'])
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

@patient_bp.route('/api/patient/notifications/<int:notif_id>', methods=['DELETE'])
@patient_required
def delete_patient_notification(notif_id):
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM notifications WHERE id = %s AND recipient_type = 'patient' AND recipient_id = %s",
              (notif_id, patient_id))
    conn.close()
    return jsonify({'message': 'Deleted'})

@patient_bp.route('/api/patient/notifications', methods=['DELETE'])
@patient_required
def delete_all_patient_notifications():
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM notifications WHERE recipient_type = 'patient' AND recipient_id = %s", (patient_id,))
    conn.close()
    return jsonify({'message': 'All notifications deleted'})

@patient_bp.route('/api/chat', methods=['POST'])
@patient_required
def ai_chat():
    patient_id = get_jwt_identity()
    data       = request.json
    message    = data.get('message', '').strip()
    session_id = data.get('session_id', str(uuid.uuid4()))
    mode       = data.get('mode', 'general')
    if not message:
        return jsonify({'error': 'Message is required'}), 400

    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT first_name, last_name, dob, gender, blood_group FROM patients WHERE id = %s", (patient_id,))
    patient = c.fetchone()

    c.execute("""
        SELECT mr.diagnosis, mr.prescription, a.appointment_date, h.name as hospital_name
        FROM medical_records mr
        JOIN appointments a ON mr.appointment_id = a.id
        JOIN hospitals h ON mr.hospital_id = h.id
        WHERE mr.patient_id = %s ORDER BY mr.created_at DESC LIMIT 5
    """, (patient_id,))
    records = c.fetchall()

    c.execute("""
        SELECT role, message FROM conversations
        WHERE patient_id = %s AND session_id = %s
        ORDER BY created_at DESC LIMIT 10
    """, (patient_id, session_id))
    history = list(reversed(c.fetchall()))
    conn.close()

    age = None
    if patient and patient.get('dob'):
        age = (datetime.now().date() - patient['dob']).days // 365

    context = []
    if patient:
        context.append(f"Patient: {patient['first_name']} {patient['last_name']}, Age: {age or 'Unknown'}, Gender: {patient.get('gender','Unknown')}, Blood Group: {patient.get('blood_group','Unknown')}")
    if records:
        context.append("Recent Medical History:")
        for r in records:
            context.append(f"- {str(r.get('appointment_date',''))[:10]} at {r.get('hospital_name','')}: Diagnosis: {r.get('diagnosis','N/A')}, Prescription: {r.get('prescription','N/A')}")

    mode_prompts = {
        'general':    "You are a helpful medical assistant. Provide clear, concise, practical health information. Always recommend consulting a doctor for serious concerns.",
        'symptoms':   "You are a symptom analysis assistant. Assess the described symptoms, list possible causes, and indicate urgency level (low/medium/high). Always recommend professional evaluation.",
        'medication': "You are a medication information assistant. Provide accurate medication details including dosages, side effects, and interactions. Always advise medical supervision.",
        'health':     "You are a wellness advisor. Provide preventive health tips and lifestyle guidance in clear bullet points."
    }
    system_prompt = mode_prompts.get(mode, mode_prompts['general'])
    if context:
        system_prompt += "\n\nPatient Context:\n" + "\n".join(context)

    history_text = "\n".join(f"{h['role'].title()}: {h['message']}" for h in history[-6:])
    full_prompt  = f"{history_text}\nUser: {message}" if history_text else message

    def generate():
        full_reply = []
        try:
            client = Groq(api_key=Config.GROQ_API_KEY)
            stream = client.chat.completions.create(
                model='llama-3.3-70b-versatile',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user',   'content': full_prompt}
                ],
                max_tokens=1024,
                temperature=0.7,
                stream=True
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    full_reply.append(token)
                    yield f"data: {json.dumps({'token': token, 'session_id': session_id})}\n\n"

            reply = ''.join(full_reply)
            save_conn = get_db()
            save_c = save_conn.cursor()
            save_c.execute("INSERT INTO conversations (patient_id, session_id, role, message) VALUES (%s,%s,'user',%s)",
                           (patient_id, session_id, message))
            save_c.execute("INSERT INTO conversations (patient_id, session_id, role, message) VALUES (%s,%s,'assistant',%s)",
                           (patient_id, session_id, reply))
            save_c.execute("SELECT COUNT(*) FROM chat_sessions WHERE session_id = %s", (session_id,))
            is_new = save_c.fetchone()[0] == 0
            if is_new:
                try:
                    title_resp = client.chat.completions.create(
                        model='llama-3.1-8b-instant',
                        messages=[
                            {'role': 'system', 'content': 'Create a short 4-6 word title for this chat based on the user message. Return only the title, no quotes, no punctuation at the end.'},
                            {'role': 'user', 'content': message[:300]}
                        ],
                        max_tokens=20, temperature=0.3
                    )
                    title = title_resp.choices[0].message.content.strip()[:100]
                except Exception:
                    title = message[:60].strip()
                save_c.execute("INSERT INTO chat_sessions (session_id, patient_id, title) VALUES (%s,%s,%s)",
                               (session_id, patient_id, title))
            save_conn.close()
            yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"

        except Exception as e:
            print(f"[CHAT ERROR] {type(e).__name__}: {str(e)[:200]}")
            yield f"data: {json.dumps({'error': 'AI service error. Please try again.'})}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@patient_bp.route('/api/chat/sessions', methods=['GET'])
@patient_required
def get_chat_sessions():
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT cs.session_id AS id, cs.title, cs.created_at
        FROM chat_sessions cs
        WHERE cs.patient_id = %s
        ORDER BY cs.created_at DESC LIMIT 30
    """, (patient_id,))
    sessions = c.fetchall()
    conn.close()
    return jsonify(serialize(sessions))

@patient_bp.route('/api/chat/sessions/<session_id>', methods=['GET'])
@patient_required
def get_chat_session(session_id):
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT role, message AS content, created_at FROM conversations
        WHERE patient_id = %s AND session_id = %s ORDER BY created_at ASC
    """, (patient_id, session_id))
    messages = c.fetchall()
    c.execute("SELECT title FROM chat_sessions WHERE session_id = %s AND patient_id = %s LIMIT 1",
              (session_id, patient_id))
    row = c.fetchone()
    conn.close()
    return jsonify({'messages': serialize(messages), 'title': row['title'] if row else 'Chat Session'})

@patient_bp.route('/api/chat/sessions/<session_id>', methods=['DELETE'])
@patient_required
def delete_chat_session(session_id):
    patient_id = get_jwt_identity()
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM conversations WHERE patient_id = %s AND session_id = %s", (patient_id, session_id))
    c.execute("DELETE FROM chat_sessions WHERE patient_id = %s AND session_id = %s", (patient_id, session_id))
    conn.close()
    return jsonify({'message': 'Session deleted'})
