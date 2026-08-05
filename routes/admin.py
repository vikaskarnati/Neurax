"""
Admin routes blueprint.
Provides endpoints for the administrative dashboard, including system-wide statistics, hospital approvals, and audit logs.
"""
from flask import Blueprint, jsonify
from database import get_db, admin_required
from utils.helpers import serialize
import json

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT COUNT(*) as t FROM hospitals");    total_h = c.fetchone()['t']
    c.execute("SELECT COUNT(*) as t FROM patients");     total_p = c.fetchone()['t']
    c.execute("SELECT COUNT(*) as t FROM appointments"); total_a = c.fetchone()['t']
    conn.close()
    return jsonify({
        'total_hospitals':    total_h,
        'total_patients':     total_p,
        'total_appointments': total_a
    })

@admin_bp.route('/api/admin/hospitals', methods=['GET'])
@admin_required
def admin_get_hospitals():
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("""
        SELECT h.id, h.name, h.type, h.hospital_code, h.city, h.state,
               h.email, h.phone, h.created_at,
               COUNT(a.id) as total_appointments
        FROM hospitals h
        LEFT JOIN appointments a ON h.id = a.hospital_id
        GROUP BY h.id ORDER BY h.created_at DESC
    """)
    hospitals = c.fetchall()
    conn.close()
    return jsonify(serialize(hospitals))


@admin_bp.route('/api/admin/audit-logs', methods=['GET'])
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
