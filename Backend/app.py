from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from datetime import datetime
import os
import re
import pytesseract
from PIL import Image

from predict import predict
from knowledge import knowledge_store

# Use TESSERACT_CMD env var on Linux/Render; fall back to system PATH default
pytesseract.pytesseract.tesseract_cmd = os.environ.get("TESSERACT_CMD", "tesseract")

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_FOLDER = os.path.join(BASE_DIR, "..", "Front end final")

# Startup diagnostics — visible in Render/gunicorn logs immediately
_gemini_key_present = bool(os.environ.get("GEMINI_API_KEY", "").strip())
print(f"[helia] GEMINI_API_KEY found: {_gemini_key_present}")
if not _gemini_key_present:
    print("[helia] WARNING: GEMINI_API_KEY not set — chatbot will use keyword fallback only")

try:
    import google.generativeai as _genai_test   # noqa: F401
    print("[helia] google-generativeai: import OK")
except ImportError as _e:
    print(f"[helia] google-generativeai: IMPORT FAILED — {_e}")


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
@app.route('/energy.html')
@app.route('/energy-usage')
@app.route('/energy-usage.html')
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
def parse_bill_text(text):
    units_consumed = None
    bill_amount = None
    billing_period = None

    unit_patterns = [
        r'units?\s+consumed[:\s]+(\d+(?:\.\d+)?)',
        r'energy\s+consumed[:\s]+(\d+(?:\.\d+)?)',
        r'consumption[:\s]+(\d+(?:\.\d+)?)\s*kwh',
        r'(\d+(?:\.\d+)?)\s+units?\b',
    ]
    for pat in unit_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                units_consumed = float(m.group(1))
                break
            except ValueError:
                pass

    amount_patterns = [
        r'(?:net\s+)?bill\s+amount[:\s]+(?:rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)',
        r'total\s+amount[:\s]+(?:rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)',
        r'amount\s+payable[:\s]+(?:rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)',
        r'(?:rs\.?|₹)\s*(\d[\d,]*(?:\.\d+)?)',
    ]
    for pat in amount_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                bill_amount = float(m.group(1).replace(',', ''))
                break
            except ValueError:
                pass

    period_patterns = [
        r'billing\s+period[:\s]+(.+?)(?:\n|$)',
        r'(?:from|period)[:\s]+(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})\s+to\s+(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})',
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}',
    ]
    for pat in period_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            billing_period = (f"{m.group(1)} to {m.group(2)}" if m.lastindex == 2 else m.group(1)).strip()
            break

    return units_consumed, bill_amount, billing_period


@app.route("/upload-bill", methods=["POST"])
def upload_bill():
    try:
        if 'bill' not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400

        file = request.files["bill"]
        filename = (file.filename or '').lower()

        if filename.endswith('.pdf'):
            return jsonify({
                "success": False,
                "error": "PDF files are not supported. Please upload a JPG or PNG image of your bill."
            }), 400

        image = Image.open(file)
        text = pytesseract.image_to_string(image)

        units_consumed, bill_amount, billing_period = parse_bill_text(text)

        return jsonify({
            "success": True,
            "text": text,
            "units_consumed": units_consumed,
            "bill_amount": bill_amount,
            "billing_period": billing_period
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# ==========================
# ROOFTOP ANALYSIS API
# ==========================

@app.route('/analyze-rooftop', methods=['POST'])
def analyze_rooftop_endpoint():
    try:
        from rooftop_analysis import analyze_rooftop
    except Exception as e:
        return jsonify({'success': False, 'error': 'Analysis module unavailable: ' + str(e)}), 503
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file provided'}), 400
        result = analyze_rooftop(request.files['image'])
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
        print("[predict] PREDICT-SOLAR REQUEST RECEIVED")
        data = request.get_json(force=True, silent=True)

        if data is None:
            print("[predict] ERROR: No valid JSON body")
            return jsonify({"error": "Request body must be valid JSON."}), 400

        print("[predict] Inputs:", {
            "latitude":       data.get("latitude"),
            "longitude":      data.get("longitude"),
            "temperature":    data.get("temperature"),
            "humidity":       data.get("humidity"),
            "wind_speed":     data.get("wind_speed"),
            "cloud_cover_pct": data.get("cloud_cover_pct"),
        })

        required = ["latitude", "longitude", "temperature", "humidity", "wind_speed"]
        missing = [f for f in required if f not in data]
        if missing:
            print("[predict] ERROR: Missing fields:", missing)
            return jsonify({"error": f"Missing fields: {missing}"}), 422

        lat  = float(data["latitude"])
        lon  = float(data["longitude"])
        temp = float(data["temperature"])
        hum  = float(data["humidity"])
        ws   = float(data["wind_speed"])

        date = None
        if data.get("date"):
            date = datetime.strptime(data["date"], "%Y-%m-%d")

        cloud_cover_pct = None
        if data.get("cloud_cover_pct") is not None:
            cloud_cover_pct = float(data["cloud_cover_pct"])

        print("[predict] CALLING predict()...")
        result = predict(
            latitude=lat,
            longitude=lon,
            temperature=temp,
            humidity=hum,
            wind_speed=ws,
            date=date,
            cloud_cover_pct=cloud_cover_pct,
        )

        print("[predict] SUCCESS:", {
            "potential_score":      result.get("potential_score"),
            "peak_sun_hours":       result.get("peak_sun_hours"),
            "recommended_capacity": result.get("recommended_capacity"),
            "panel_count":          result.get("panel_count"),
            "annual_projection":    result.get("annual_projection"),
            "energy_coverage":      result.get("energy_coverage"),
            "suitability":          result.get("suitability"),
            "confidence":           result.get("confidence"),
        })

        # ── Pre-serialisation safety check ───────────────────────────────────
        # jsonify() in Flask 3.x can raise AFTER committing the 200 status line
        # if any value is non-serialisable (numpy scalar, NaN, Inf, etc.).
        # Verify here first so any failure returns a proper 500 with a body.
        import json as _json
        try:
            _body_str = _json.dumps(result)
            print("[predict-solar] returning: JSON OK, byte count:", len(_body_str))
            print("[predict-solar] Content-Type will be: application/json")
            print("[predict-solar] returning:", result)
        except (TypeError, ValueError) as _json_err:
            print("[predict-solar] JSON SERIALISATION FAILED:", type(_json_err).__name__, str(_json_err))
            print("[predict-solar] type map:", {k: type(v).__name__ for k, v in result.items()})
            # Surface as a proper 500 with a body so the browser never gets an empty 200
            return jsonify({"error": "Internal serialisation error", "detail": str(_json_err)}), 500

        resp = jsonify(result)
        print(
            "[predict-solar] response object: status=%s content_type=%s content_length=%s",
            resp.status_code,
            resp.content_type,
            resp.content_length,
        )
        return resp

    except FileNotFoundError as e:
        print("[predict-solar] returning: FileNotFoundError —", str(e))
        return jsonify({"error": str(e), "hint": "Run train_model.py first"}), 503

    except Exception as e:
        import traceback
        print("[predict-solar] returning: unhandled exception —", type(e).__name__, str(e))
        print("[predict] UNHANDLED EXCEPTION:")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/<path:path>', methods=['GET'])
def static_files(path):
    requested_path = os.path.join(FRONTEND_FOLDER, path)
    if os.path.exists(requested_path):
        return send_from_directory(FRONTEND_FOLDER, path)
    # If the requested path does not exist, fallback to the frontend index for client-side navigation.
    index_path = os.path.join(FRONTEND_FOLDER, 'index.html')
    if os.path.exists(index_path):
        return send_from_directory(FRONTEND_FOLDER, 'index.html')
    return jsonify({"error": "File not found"}), 404

# ==========================
# HELIA AI — GEMINI BACKEND
# ==========================

_SYSTEM_PROMPT = (
    "You are Helia, a friendly and knowledgeable solar energy consultant at HelioSense AI — "
    "a platform helping Indian households and businesses plan and switch to solar.\n\n"

    "TONE AND STYLE:\n"
    "- Speak like a helpful consultant talking to a customer, not a textbook or manual\n"
    "- Be warm, clear, and direct — like a knowledgeable friend who knows solar\n"
    "- Keep most answers to 3–5 sentences or under ~150 words\n"
    "- Use bullet points (•) only when listing multiple distinct items\n"
    "- Write short paragraphs, not walls of text\n"
    "- If the user asks for more detail, you may go longer\n\n"

    "WHAT NEVER TO SAY:\n"
    "- Never say 'From the knowledge base', 'According to the document', "
    "'The uploaded file states', 'retrieved context', or any reference to PDFs, "
    "source files, or chunks — just answer naturally as a consultant would\n"
    "- Never use passive, robotic phrases like 'A solar system may generate...'\n\n"

    "HOW TO USE THE USER'S DATA:\n"
    "- When the user's analysis results are provided, always reference those real numbers naturally\n"
    "- Example: instead of 'A solar system may generate...', say "
    "'Based on your analysis, your recommended system is 8.4 kW and could generate "
    "around 12,400 kWh per year.'\n"
    "- Never fabricate figures. If specific data is not available, say so plainly and move on\n\n"

    "YOUR AREAS OF EXPERTISE:\n"
    "- Solar system sizing, panel count, capacity, and performance\n"
    "- Rooftop analysis: total area, usable area, obstructions, shading, suitability\n"
    "- Financial planning: installation cost, ROI, payback period, annual savings\n"
    "- Net metering and grid-tied solar systems\n"
    "- Indian government schemes: PM Surya Ghar, MNRE subsidies, DISCOM regulations\n"
    "- Electricity bill analysis and consumption-based sizing\n\n"

    "Use ₹ for currency. Keep it conversational and genuinely helpful."
)


def _fmt_prediction(p):
    if not isinstance(p, dict):
        return ''
    lines = []
    if p.get('predicted_irradiance') is not None:
        lines.append(f"Solar Irradiance: {p['predicted_irradiance']} kWh/m²/day")
    if p.get('potential_score') is not None:
        lines.append(f"Solar Potential Score: {p['potential_score']}/100")
    if p.get('peak_sun_hours') is not None:
        lines.append(f"Peak Sun Hours: {p['peak_sun_hours']} hrs/day")
    if p.get('recommended_capacity') is not None:
        lines.append(f"Recommended System Capacity: {p['recommended_capacity']} kW")
    if p.get('annual_projection') is not None:
        lines.append(f"Annual Energy Generation: {p['annual_projection']} kWh/year")
    if p.get('energy_coverage') is not None:
        lines.append(f"Energy Coverage of Demand: {p['energy_coverage']}%")
    if p.get('suitability') is not None:
        lines.append(f"Suitability Rating: {p['suitability']}")
    if isinstance(p.get('inputs'), dict):
        inp = p['inputs']
        parts = []
        if inp.get('latitude'):  parts.append(f"lat={inp['latitude']}")
        if inp.get('longitude'): parts.append(f"lon={inp['longitude']}")
        if inp.get('temperature') is not None: parts.append(f"temp={inp['temperature']}°C")
        if inp.get('humidity') is not None: parts.append(f"humidity={inp['humidity']}%")
        if inp.get('cloud_cover_pct') is not None: parts.append(f"cloud={inp['cloud_cover_pct']}%")
        if parts:
            lines.append(f"Input conditions: {', '.join(parts)}")
    return '\n'.join(lines)


def _fmt_rooftop(r):
    if not isinstance(r, dict):
        return ''
    lines = []
    if r.get('roof_area_m2') is not None:
        lines.append(f"Total Roof Area: {r['roof_area_m2']} m²")
    if r.get('usable_area_m2') is not None:
        lines.append(f"Usable Solar Area: {r['usable_area_m2']} m²")
    if r.get('setback_area_m2') is not None:
        lines.append(f"Edge Setback Area: {r['setback_area_m2']} m²")
    if r.get('obstruction_area_m2') is not None:
        lines.append(f"Obstruction Area: {r['obstruction_area_m2']} m²")
    if r.get('suitability_score') is not None:
        lines.append(f"Suitability Score: {r['suitability_score']}/100")
    if r.get('shade_risk') is not None:
        lines.append(f"Shade Risk: {r['shade_risk']}")
    if r.get('obstruction_count') is not None:
        lines.append(f"Obstructions Detected: {r['obstruction_count']}")
    if r.get('recommended_capacity_kw') is not None:
        lines.append(f"Recommended Capacity: {r['recommended_capacity_kw']} kW")
    if r.get('panel_count') is not None:
        lines.append(f"Recommended Panel Count: {r['panel_count']}")
    if r.get('confidence') is not None:
        lines.append(f"Analysis Confidence: {r['confidence']}%")
    if r.get('analysis_method'):
        lines.append(f"Detection Method: {r['analysis_method']}")
    return '\n'.join(lines)


def _fmt_roi(r):
    if not isinstance(r, dict):
        return ''
    lines = []
    try:
        if r.get('installation_cost') is not None:
            lines.append(f"Installation Cost: ₹{float(r['installation_cost']):,.0f}")
        if r.get('annual_savings') is not None:
            lines.append(f"Annual Savings: ₹{float(r['annual_savings']):,.0f}")
        if r.get('payback_period') is not None:
            lines.append(f"Payback Period: {float(r['payback_period']):.1f} years")
        if r.get('roi_percentage') is not None:
            lines.append(f"ROI: {float(r['roi_percentage']):.1f}%")
        if r.get('lifetime_savings') is not None:
            lines.append(f"25-Year Lifetime Savings: ₹{float(r['lifetime_savings']):,.0f}")
    except (TypeError, ValueError):
        pass
    return '\n'.join(lines)


def _gemini_answer(question, prediction, rooftop, roi, chunks, history):
    """Call Gemini 1.5 Flash. Returns None if key is missing or call fails."""
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            system_instruction=_SYSTEM_PROMPT,
            generation_config=genai.types.GenerationConfig(
                temperature=0.5,
                max_output_tokens=500,
            ),
        )

        ctx_sections = []
        if chunks:
            kb = '\n'.join(c['chunk'] for c in chunks)
            ctx_sections.append(
                f"BACKGROUND INFO (internal — do not cite or mention the source; "
                f"weave into your answer naturally):\n{kb}"
            )
        pred_str = _fmt_prediction(prediction)
        if pred_str:
            ctx_sections.append(f"USER'S SOLAR PREDICTION:\n{pred_str}")
        roof_str = _fmt_rooftop(rooftop)
        if roof_str:
            ctx_sections.append(f"USER'S ROOFTOP ANALYSIS:\n{roof_str}")
        roi_str = _fmt_roi(roi)
        if roi_str:
            ctx_sections.append(f"USER'S ROI DATA:\n{roi_str}")

        context_block = '\n\n'.join(ctx_sections)

        # Convert history for Gemini — must alternate user/model, starting with user
        gemini_history = []
        expected = 'user'
        for msg in (history or [])[-10:]:
            role = msg.get('role', '')
            text = (msg.get('text') or '').strip()
            gemini_role = 'user' if role == 'user' else 'model'
            if gemini_role != expected or not text:
                continue
            gemini_history.append({'role': gemini_role, 'parts': [text]})
            expected = 'model' if expected == 'user' else 'user'

        chat = model.start_chat(history=gemini_history)
        full_msg = f"{context_block}\n\nQuestion: {question}" if context_block else question
        resp = chat.send_message(full_msg)
        return resp.text.strip()

    except Exception as exc:
        app.logger.warning('Gemini error: %s', exc)
        return None


def _fallback_answer(question, prediction, roi, chunks):
    """Keyword-based fallback when Gemini is unavailable."""
    text = question.lower()

    if any(g in text for g in ['hi', 'hello', 'hey', 'good morning', 'good evening']):
        return (
            "Hello! I'm Helia AI, your solar planning consultant. "
            "Ask me about solar predictions, ROI, rooftop analysis, subsidies, or net metering."
        )
    if 'thank' in text:
        return "You're welcome! Feel free to ask more solar planning questions."

    if any(k in text for k in ['explain', 'prediction', 'forecast', 'irradiance', 'peak sun', 'score', 'coverage']):
        if isinstance(prediction, dict) and prediction.get('potential_score') is not None:
            score  = prediction.get('potential_score', 'N/A')
            cap    = prediction.get('recommended_capacity', 'N/A')
            annual = prediction.get('annual_projection', 'N/A')
            irr    = prediction.get('predicted_irradiance', 'N/A')
            return (
                f"Your location has a solar potential score of {score}/100 with "
                f"{irr} kWh/m²/day irradiance. "
                f"A {cap} kW system is recommended, generating ~{annual} kWh/year."
            )

    if any(k in text for k in ['roi', 'return', 'payback', 'savings', 'cost', 'investment', 'break']):
        if isinstance(roi, dict) and roi.get('payback_period') is not None:
            try:
                pb  = float(roi['payback_period'])
                sav = float(roi.get('annual_savings', 0))
                return (
                    f"Your system has a payback period of {pb:.1f} years "
                    f"with annual savings of ₹{sav:,.0f}."
                )
            except (TypeError, ValueError):
                pass

    return (
        "That's a good question — I'd need a bit more context to give you a precise answer. "
        "I can help with solar system sizing, rooftop suitability, ROI, PM Surya Ghar subsidies, "
        "and net metering. Could you tell me a bit more about what you're looking for?"
    )


@app.route('/chat-query', methods=['POST'])
def chat_query():
    try:
        print("[helia] CHAT REQUEST RECEIVED")
        data = request.get_json(force=True, silent=True) or {}
        print("[helia] REQUEST BODY:", {
            'question':   (data.get('question') or '')[:120],
            'prediction': bool(data.get('prediction')),
            'rooftop':    bool(data.get('rooftop')),
            'roi':        bool(data.get('roi')),
            'history_len': len(data.get('history') or []),
        })

        question   = (data.get('question') or '').strip()
        prediction = data.get('prediction')
        rooftop    = data.get('rooftop')
        roi        = data.get('roi')
        history    = data.get('history') or []

        if not question:
            print("[helia] Empty question — returning 400")
            return jsonify({
                'answer': 'Please type a question so I can help you.',
                'chunks': [],
                'sources': [],
            }), 400

        chunks = knowledge_store.retrieve(question, top_k=3)
        print(f"[helia] KB chunks retrieved: {len(chunks)}")

        print("[helia] CALLING GEMINI")
        answer = _gemini_answer(question, prediction, rooftop, roi, chunks, history)
        print(f"[helia] GEMINI RESPONSE: {repr(answer[:120]) if answer else None}")

        if answer is None:
            print("[helia] Gemini returned None — using keyword fallback")
            answer = _fallback_answer(question, prediction, roi, chunks)
            print(f"[helia] FALLBACK ANSWER: {repr(answer[:120])}")

        print(f"[helia] Returning answer ({len(answer)} chars)")
        return jsonify({
            'answer':  answer,
            'chunks':  chunks,
            'sources': [f"{c['source']} (page {c['page']})" for c in chunks],
        })

    except Exception as e:
        import traceback
        print("[helia] UNHANDLED EXCEPTION in /chat-query:")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error':   str(e),
            'answer':  'An internal error occurred. Check the server logs.',
            'chunks':  [],
            'sources': [],
        }), 500

# ==========================
# START SERVER
# ==========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    print("\n" + "="*60)
    print("HelioSense AI Running")
    print(f"Home       : http://localhost:{port}")
    print(f"Prediction : http://localhost:{port}/prediction")
    print(f"Health     : http://localhost:{port}/health")
    print("="*60 + "\n")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True,
        use_reloader=False
    )