from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from datetime import datetime
import traceback
import os

from predict import predict
from knowledge import knowledge_store

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_FOLDER = os.path.join(BASE_DIR, "..", "Front end final")


# ==========================
# WEBSITE ROUTES
# ==========================

@app.route('/')
def home():
    return send_from_directory(FRONTEND_FOLDER, 'index.html')

@app.route('/login')
def login():
    return send_from_directory(FRONTEND_FOLDER, 'login.html')

@app.route('/register')
def register():
    return send_from_directory(FRONTEND_FOLDER, 'register.html')

@app.route('/dashboard')
def dashboard():
    return send_from_directory(FRONTEND_FOLDER, 'dashboard.html')

@app.route('/analysis')
def analysis():
    return send_from_directory(FRONTEND_FOLDER, 'analysis.html')

@app.route('/energy')
def energy():
    return send_from_directory(FRONTEND_FOLDER, 'energy-usage.html')

@app.route('/prediction')
def prediction_page():
    return send_from_directory(FRONTEND_FOLDER, 'prediction.html')

@app.route('/roi')
def roi():
    return send_from_directory(FRONTEND_FOLDER, 'roi.html')

@app.route('/reports')
def reports():
    return send_from_directory(FRONTEND_FOLDER, 'reports.html')

@app.route('/chatbot')
def chatbot():
    return send_from_directory(FRONTEND_FOLDER, 'chatbot.html')

@app.route("/debug")
def debug():
    return jsonify({
        "base_dir": BASE_DIR,
        "frontend_folder": FRONTEND_FOLDER,
        "exists": os.path.exists(FRONTEND_FOLDER),
        "files": os.listdir(FRONTEND_FOLDER) if os.path.exists(FRONTEND_FOLDER) else []
    })
# ==========================
# STATIC FILES
# ==========================

@app.route('/css/<path:filename>')
def css_files(filename):
    return send_from_directory(
        os.path.join(FRONTEND_FOLDER, 'css'),
        filename
    )

@app.route('/js/<path:filename>')
def js_files(filename):
    return send_from_directory(
        os.path.join(FRONTEND_FOLDER, 'js'),
        filename
    )

@app.route('/assets/<path:filename>')
def assets_files(filename):
    return send_from_directory(
        os.path.join(FRONTEND_FOLDER, 'assets'),
        filename
    )

# ==========================
# HEALTH CHECK
# ==========================

@app.route("/health")
def health():
    return {
        "status": "ok",
        "service": "Helia AI Backend"
    }

# ==========================
# SOLAR PREDICTION API
# ==========================

@app.route("/predict-solar", methods=["POST"])
def predict_solar():

    try:
        data = request.get_json(force=True, silent=True)

        if data is None:
            return jsonify({
                "error": "Request body must be valid JSON."
            }), 400

        required = [
            "latitude",
            "longitude",
            "temperature",
            "humidity",
            "wind_speed"
        ]

        missing = [
            field for field in required
            if field not in data
        ]

        if missing:
            return jsonify({
                "error": f"Missing fields: {missing}"
            }), 422

        lat = float(data["latitude"])
        lon = float(data["longitude"])
        temp = float(data["temperature"])
        hum = float(data["humidity"])
        ws = float(data["wind_speed"])

        date = None

        if data.get("date"):
            date = datetime.strptime(
                data["date"],
                "%Y-%m-%d"
            )

        result = predict(
            latitude=lat,
            longitude=lon,
            temperature=temp,
            humidity=hum,
            wind_speed=ws,
            date=date
        )

        return jsonify(result)

    except FileNotFoundError as e:

        return jsonify({
            "error": str(e),
            "hint": "Run train_model.py first"
        }), 503

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(FRONTEND_FOLDER, path)

@app.route('/chat-query', methods=['POST'])
def chat_query():
    data = request.get_json(force=True, silent=True) or {}
    question = (data.get('question') or '').strip()
    prediction = data.get('prediction')
    roi = data.get('roi')

    if not question:
        return jsonify({
            'answer': 'Please type a question so I can help you with solar predictions, ROI, or rooftop planning.',
            'chunks': [],
            'sources': []
        }), 400

    app.logger.info('User Message: %s', question)

    chunks = knowledge_store.retrieve(question, top_k=4)
    app.logger.info('Retrieved Chunks: %s', chunks)

    answer, used_prediction, used_roi = compose_answer(question, prediction, roi, chunks)

    response = {
        'answer': answer,
        'chunks': chunks,
        'sources': [f"{chunk['source']} (page {chunk['page']})" for chunk in chunks],
        'prediction': used_prediction,
        'roi': used_roi
    }
    return jsonify(response)


def safe_number(value, digits=1):
    try:
        return float(value)
    except Exception:
        return None


def format_inr(value):
    try:
        amount = float(value)
        return f"₹{amount:,.0f}"
    except Exception:
        return 'N/A'


def derive_roi(prediction_data):
    if not isinstance(prediction_data, dict):
        return None
    cap = safe_number(prediction_data.get('recommended_capacity'))
    annual = safe_number(prediction_data.get('annual_projection'))
    if not cap or not annual or annual <= 0:
        return None
    installation_cost = cap * 55000
    annual_savings = annual * 7
    lifetime_savings = annual_savings * 25
    payback_period = installation_cost / annual_savings if annual_savings > 0 else None
    roi_percentage = (annual_savings / installation_cost * 100) if installation_cost > 0 else None
    break_even = f"in about {payback_period:.1f} years" if payback_period is not None else 'N/A'
    return {
        'installation_cost': installation_cost,
        'annual_savings': annual_savings,
        'lifetime_savings': lifetime_savings,
        'payback_period': payback_period,
        'roi_percentage': roi_percentage,
        'break_even_date': break_even
    }


def compose_answer(question, prediction, roi, chunks):
    text = question.lower()
    greeting_keywords = ['hi', 'hello', 'hey', 'good morning', 'good evening', 'how are you', 'how are you?']
    if any(keyword in text for keyword in greeting_keywords):
        return ("Hello! I'm Helia AI ☀️ I’m here to help you with solar prediction, ROI analysis, and rooftop solar planning. "
                "What would you like to explore today?" , prediction, roi)

    if 'thank' in text:
        return ('You’re welcome! If you have more solar questions, I’m here to help. 😊', prediction, roi)

    if any(keyword in text for keyword in ['bye', 'goodbye', 'see you']):
        return ('Thank you for visiting Helia AI. Have a wonderful day and feel free to return anytime if you need solar guidance. ☀️', prediction, roi)

    if any(keyword in text for keyword in ['show my prediction', 'prediction dashboard', 'view prediction', 'prediction page']):
        return ('You can view your solar prediction here:\nPrediction Dashboard → /prediction', prediction, roi)

    if any(keyword in text for keyword in ['show roi', 'roi dashboard', 'view roi', 'financial analysis']):
        return ('You can review your financial analysis here:\nROI Dashboard → /roi', prediction, roi)

    if any(keyword in text for keyword in ['show report', 'reports', 'report page', 'download report']):
        return ('Your generated report is available in:\nReports → /reports', prediction, roi)

    if any(keyword in text for keyword in ['explain my prediction', 'prediction result', 'solar prediction', 'annual generation', 'peak sun hours', 'recommended capacity', 'panel count', 'energy coverage']):
        if prediction and isinstance(prediction, dict):
            score = prediction.get('potential_score', 'N/A')
            annual_projection = prediction.get('annual_projection', 'N/A')
            peak = prediction.get('peak_sun_hours', 'N/A')
            capacity = prediction.get('recommended_capacity', 'N/A')
            panels = prediction.get('panel_count', 'N/A')
            coverage = prediction.get('energy_coverage', 'N/A')
            return (f"Based on your assessment:\n"
                    f"• Solar Potential Score: {score}/100\n"
                    f"• Annual Generation: {annual_projection} kWh\n"
                    f"• Peak Sun Hours: {peak}\n"
                    f"• Recommended Capacity: {capacity} kW\n"
                    f"• Panel Count: {panels}\n"
                    f"• Energy Coverage: {coverage}%\n\n"
                    "Your location shows strong solar potential and is suitable for rooftop solar installation.", prediction, roi)
        return ('I don\'t currently have enough information to explain your prediction accurately. Please generate a solar assessment first.', prediction, roi)

    resolved_roi = roi if isinstance(roi, dict) else derive_roi(prediction)
    if any(keyword in text for keyword in ['explain roi', 'why is my roi', 'payback period', 'annual savings', 'lifetime savings', 'break-even', 'installation cost']):
        if resolved_roi and isinstance(resolved_roi, dict):
            return (f"Your ROI is calculated based on annual savings compared to installation cost.\n\n"
                    f"Installation Cost: {format_inr(resolved_roi.get('installation_cost'))}\n"
                    f"Annual Savings: {format_inr(resolved_roi.get('annual_savings'))}\n"
                    f"ROI Percentage: {resolved_roi.get('roi_percentage'):.1f}%\n"
                    f"Payback Period: {resolved_roi.get('payback_period'):.1f} years\n"
                    f"Lifetime Savings: {format_inr(resolved_roi.get('lifetime_savings'))}\n"
                    f"Break-even Date: {resolved_roi.get('break_even_date')}\n\n"
                    "This investment is expected to recover in around "
                    f"{resolved_roi.get('payback_period'):.1f} years.", prediction, resolved_roi)
        return ('I don\'t currently have enough information to answer that accurately. Please generate a solar assessment first.', prediction, roi)

    if chunks:
        snippet_lines = []
        for chunk in chunks[:3]:
            snippet = chunk.get('chunk', '').strip()
            if snippet:
                snippet_lines.append(snippet)
        joined = '\n\n'.join(snippet_lines)
        base = 'I found this information in the Helia Doc knowledge base:'
        return (f"{base}\n\n{joined}", prediction, roi)

    return ('I don\'t currently have enough information to answer that accurately. Please generate a solar assessment first.', prediction, roi)

# ==========================
# START SERVER
# ==========================

if __name__ == "__main__":

    print("\n" + "="*60)
    print("HelioSense AI Running")
    print("Home       : http://127.0.0.1:5000")
    print("Prediction : http://127.0.0.1:5000/prediction")
    print("Health     : http://127.0.0.1:5000/health")
    print("="*60 + "\n")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False
    )
