from flask import Blueprint, request, send_file, jsonify
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io

report_bp = Blueprint('report', __name__)


@report_bp.route('/generate', methods=['POST'])
def generate_report():
    data = request.json or {}
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont('Helvetica', 14)
    c.drawString(50, 800, 'Helia AI - Solar Assessment Report')
    y = 760
    for k, v in data.items():
        c.setFont('Helvetica', 11)
        c.drawString(50, y, f"{k}: {v}")
        y -= 20
    c.showPage()
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='helia_report.pdf', mimetype='application/pdf')
