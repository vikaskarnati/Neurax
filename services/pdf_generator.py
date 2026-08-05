"""
PDF generation service.
Utilizes ReportLab to dynamically generate downloadable patient medical history cards in PDF format.
"""
import io
from flask import send_file
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.units import mm
from datetime import datetime

def generate_patient_card_pdf(patient, appointments, medical_records):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()

    title_style   = ParagraphStyle('T', parent=styles['Title'],
                                   textColor=colors.HexColor('#007AFF'), fontSize=24, spaceAfter=4)
    sub_style     = ParagraphStyle('S', parent=styles['Normal'],
                                   textColor=colors.HexColor('#8E8E93'), fontSize=11, spaceAfter=12)
    heading_style = ParagraphStyle('H', parent=styles['Heading2'],
                                   textColor=colors.HexColor('#1C1C1E'), fontSize=13, spaceBefore=14, spaceAfter=6)
    footer_style  = ParagraphStyle('F', parent=styles['Normal'],
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
        ['Blood Group',   patient.get('blood_group') or 'N/A', 'Phone', patient.get('phone') or 'N/A'],
        ['Email',         patient['email'], 'Member Since', str(patient['created_at'])[:10]],
        ['Emergency Contact', patient.get('emergency_contact_name') or 'N/A',
         'Emergency Phone',   patient.get('emergency_contact_phone') or 'N/A'],
    ]
    t = Table(info, colWidths=[38*mm, 62*mm, 38*mm, 62*mm])
    t.setStyle(TableStyle([
        ('FONTNAME',    (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',    (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, -1), 9),
        ('TEXTCOLOR',   (0, 0), (0, -1), colors.HexColor('#8E8E93')),
        ('TEXTCOLOR',   (2, 0), (2, -1), colors.HexColor('#8E8E93')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#F9F9F9'), colors.white]),
        ('GRID',        (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E5EA')),
        ('PADDING',     (0, 0), (-1, -1), 7),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t)

    if appointments:
        story.append(Paragraph("Appointment History", heading_style))
        rows = [['Hospital', 'City', 'Date', 'Time', 'Status']]
        for a in appointments:
            rows.append([
                a.get('hospital_name', ''),
                a.get('city', ''),
                str(a.get('appointment_date', ''))[:10],
                a.get('appointment_time', ''),
                (a.get('status', '')).title()
            ])
        at = Table(rows, colWidths=[55*mm, 33*mm, 28*mm, 24*mm, 28*mm])
        at.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007AFF')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9F9F9')]),
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E5EA')),
            ('PADDING',    (0, 0), (-1, -1), 6),
        ]))
        story.append(at)

    if medical_records:
        story.append(Paragraph("Medical History", heading_style))
        rec_rows = [['Date', 'Hospital', 'Diagnosis', 'Prescription', 'Notes']]
        for r in medical_records:
            import json as _json
            vitals_str = ''
            if r.get('vitals'):
                try:
                    v = _json.loads(r['vitals']) if isinstance(r['vitals'], str) else r['vitals']
                    parts = []
                    if v.get('bp'):          parts.append(f"BP:{v['bp']}")
                    if v.get('pulse'):       parts.append(f"Pulse:{v['pulse']}")
                    if v.get('temperature'): parts.append(f"Temp:{v['temperature']}°F")
                    if v.get('spo2'):        parts.append(f"SpO2:{v['spo2']}%")
                    vitals_str = '  '.join(parts)
                except Exception:
                    pass
            notes_combined = (r.get('notes') or '')
            if vitals_str:
                notes_combined = (notes_combined + '\n' + vitals_str).strip()
            rec_rows.append([
                str(r.get('appointment_date', '') or r.get('created_at', ''))[:10],
                r.get('hospital_name', ''),
                r.get('diagnosis') or '—',
                r.get('prescription') or '—',
                notes_combined or '—',
            ])
        rt = Table(rec_rows, colWidths=[22*mm, 38*mm, 38*mm, 46*mm, 36*mm])
        rt.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), colors.HexColor('#34C759')),
            ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1), 8),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, colors.HexColor('#F9F9F9')]),
            ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E5EA')),
            ('PADDING',       (0, 0), (-1, -1), 5),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('WORDWRAP',      (0, 0), (-1, -1), True),
        ]))
        story.append(rt)

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
