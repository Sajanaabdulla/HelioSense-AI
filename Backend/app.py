from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from datetime import datetime
import re
import pytesseract
from PIL import Image

from predict import predict
from knowledge import knowledge_store
import os
from dotenv import load_dotenv
load_dotenv()

print("[startup] RUNNING FILE =", os.path.abspath(__file__))

# Use TESSERACT_CMD env var on Linux/Render; fall back to system PATH default
pytesseract.pytesseract.tesseract_cmd = os.environ.get("TESSERACT_CMD", "tesseract")

app = Flask(__name__)
CORS(app)


def _safe_json_value(obj):
    """Recursively convert numpy types and non-finite floats to JSON-safe Python types.
    Prevents jsonify() from emitting invalid NaN/Infinity literals that browsers reject."""
    try:
        import numpy as np
        import math
        if isinstance(obj, dict):
            return {k: _safe_json_value(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_safe_json_value(v) for v in obj]
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            v = float(obj)
            return None if not math.isfinite(v) else v
        if isinstance(obj, np.ndarray):
            return [_safe_json_value(v) for v in obj.tolist()]
        if isinstance(obj, float) and not math.isfinite(obj):
            return None
        return obj
    except Exception:
        return str(obj)


@app.errorhandler(Exception)
def handle_unhandled_exception(e):
    """Global catch-all: ensures every unhandled error returns JSON, never HTML."""
    import traceback
    print(f"[app] UNHANDLED EXCEPTION: {type(e).__name__}: {e}")
    traceback.print_exc()
    return jsonify({"success": False, "error": "Internal server error", "detail": str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Not found"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"success": False, "error": "Method not allowed"}), 405

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_FOLDER = os.path.join(BASE_DIR, "..", "Front end final")
# In Docker (build context = Backend/), WORKDIR=/app so the parent is the
# filesystem root — not the repo root.  Try sibling paths as fallbacks.
if not os.path.exists(FRONTEND_FOLDER):
    for _candidate in [
        os.path.join(BASE_DIR, "frontend"),
        os.path.join(BASE_DIR, "..", "frontend"),
        "/app/frontend",
    ]:
        if os.path.exists(_candidate):
            FRONTEND_FOLDER = _candidate
            break

# ── Startup path diagnostics ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("[startup] HelioSense AI Backend starting up")
print(f"[startup] CWD        : {os.getcwd()}")
print(f"[startup] BASE_DIR   : {BASE_DIR}")
_sm_path   = os.path.join(BASE_DIR, "models", "solar_model.pkl")
_sm_alt    = os.path.join(BASE_DIR, "solar_model.pkl")
_cl_path   = os.path.join(BASE_DIR, "models", "climatology.pkl")
_yolo_path = os.path.abspath(
    os.path.join(BASE_DIR, "..", "runs", "detect", "train-2", "weights", "best.pt")
)
print(f"[startup] solar_model: {_sm_path} → {'EXISTS' if os.path.exists(_sm_path) else 'MISSING'}")
print(f"[startup] solar_alt  : {_sm_alt} → {'EXISTS' if os.path.exists(_sm_alt) else 'MISSING'}")
print(f"[startup] climatology: {_cl_path} → {'EXISTS' if os.path.exists(_cl_path) else 'MISSING'}")
print(f"[startup] YOLO model : {_yolo_path} → {'EXISTS' if os.path.exists(_yolo_path) else 'MISSING (OpenCV-only mode)'}")
print(f"[startup] Frontend   : {FRONTEND_FOLDER} → {'EXISTS' if os.path.exists(FRONTEND_FOLDER) else 'MISSING (HTML routes disabled)'}")
try:
    import shutil as _shutil
    _tess_binary = _shutil.which("tesseract")
    print(f"[startup] Tesseract  : {_tess_binary if _tess_binary else 'NOT FOUND (OCR falls back to demo mode)'}")
    del _shutil, _tess_binary
except Exception as _te:
    print(f"[startup] Tesseract  : check failed ({_te})")
print(f"[startup] GEMINI_KEY : {'SET' if os.environ.get('GEMINI_API_KEY') else 'NOT SET — chatbot uses keyword fallback'}")
print("=" * 60 + "\n")
del _sm_path, _sm_alt, _cl_path, _yolo_path

# ── Gemini / SDK startup diagnostics ─────────────────────────────────────────
_gemini_key_present = bool(os.environ.get("GEMINI_API_KEY", "").strip())
_gemini_key_preview = (os.environ.get("GEMINI_API_KEY", "")[:6] + "…") if _gemini_key_present else "NOT SET"
print(f"[helia] GEMINI_API_KEY: {'detected (' + _gemini_key_preview + ')' if _gemini_key_present else 'NOT SET — keyword fallback only'}")

_GEMINI_MODEL = "gemini-2.5-flash"
print(f"[helia] Gemini model selected: {_GEMINI_MODEL}")

try:
    from google import genai as _genai_probe
    from google.genai import types as _genai_types_probe  # noqa: F401
    _sdk_version = getattr(_genai_probe, "__version__", "unknown")
    print(f"[helia] google-genai SDK: import OK  version={_sdk_version}")
    if _gemini_key_present:
        try:
            _genai_probe.Client(api_key=os.environ["GEMINI_API_KEY"])
            print(f"[helia] Gemini client: initialised OK  model={_GEMINI_MODEL}")
        except Exception as _probe_err:
            print(f"[helia] Gemini client: init ERROR — {type(_probe_err).__name__}: {_probe_err}")
    del _genai_probe, _genai_types_probe
except ImportError as _e:
    print(f"[helia] google-genai SDK: IMPORT FAILED — {_e}")
    print("[helia]   → run:  pip install 'google-genai>=1.0.0'")


# ==========================
# FRONTEND HELPER
# ==========================

def _send_page(filename):
    """Serve an HTML file from FRONTEND_FOLDER; return JSON 404 when folder is absent."""
    if not os.path.exists(FRONTEND_FOLDER):
        return jsonify({
            "error": "Frontend is deployed at a separate URL",
            "frontend_url": "https://heliosense-ai-1.onrender.com",
            "missing_folder": FRONTEND_FOLDER,
        }), 404
    return send_from_directory(FRONTEND_FOLDER, filename)


# ==========================
# WEBSITE ROUTES
# ==========================

@app.route('/')
def home():
    return _send_page('index.html')

@app.route('/login')
def login():
    return _send_page('login.html')

@app.route('/register')
def register():
    return _send_page('register.html')

@app.route('/dashboard')
def dashboard():
    return _send_page('dashboard.html')

@app.route('/analysis')
def analysis():
    return _send_page('analysis.html')

@app.route('/energy')
@app.route('/energy.html')
@app.route('/energy-usage')
@app.route('/energy-usage.html')
def energy():
    return _send_page('energy-usage.html')

@app.route('/prediction')
def prediction_page():
    return _send_page('prediction.html')

@app.route('/roi')
def roi():
    return _send_page('roi.html')

@app.route('/reports')
def reports():
    return _send_page('reports.html')

@app.route('/chatbot')
def chatbot():
    return _send_page('chatbot.html')

@app.route("/debug")
def debug():
    return jsonify({
        "base_dir": BASE_DIR,
        "frontend_folder": FRONTEND_FOLDER,
        "exists": os.path.exists(FRONTEND_FOLDER),
        "files": os.listdir(FRONTEND_FOLDER) if os.path.exists(FRONTEND_FOLDER) else []
    })


@app.route("/deployment-debug")
def deployment_debug():
    import sys
    import platform
    import shutil

    _sm     = os.path.join(BASE_DIR, "models", "solar_model.pkl")
    _sm_alt = os.path.join(BASE_DIR, "solar_model.pkl")
    _cl     = os.path.join(BASE_DIR, "models", "climatology.pkl")
    _yl     = os.path.abspath(
        os.path.join(BASE_DIR, "..", "runs", "detect", "train-2", "weights", "best.pt")
    )

    try:
        _app_files = sorted(os.listdir("/app"))
    except Exception as _e:
        _app_files = [f"error listing /app: {_e}"]

    try:
        import psutil
        _mem = psutil.virtual_memory()
        _mem_info = {
            "total_mb": round(_mem.total / 1e6),
            "available_mb": round(_mem.available / 1e6),
            "percent_used": _mem.percent,
        }
    except ImportError:
        _mem_info = "psutil not installed"
    except Exception as _e:
        _mem_info = f"error: {_e}"

    return jsonify({
        "cwd": os.getcwd(),
        "base_dir": BASE_DIR,
        "python_version": sys.version,
        "platform": platform.platform(),
        "files_in_app": _app_files,
        "models_exists": os.path.exists(_sm),
        "solar_model_exists": os.path.exists(_sm) or os.path.exists(_sm_alt),
        "solar_model_path": _sm,
        "solar_model_alt_exists": os.path.exists(_sm_alt),
        "climatology_exists": os.path.exists(_cl),
        "climatology_path": _cl,
        "yolo_exists": os.path.exists(_yl),
        "yolo_path": _yl,
        "frontend_exists": os.path.exists(FRONTEND_FOLDER),
        "frontend_folder": FRONTEND_FOLDER,
        "tesseract_cmd": getattr(pytesseract.pytesseract, "tesseract_cmd", "unknown"),
        "tesseract_binary": shutil.which("tesseract"),
        "env_vars": {
            "PORT": os.environ.get("PORT"),
            "TESSERACT_CMD": os.environ.get("TESSERACT_CMD"),
            "GEMINI_API_KEY_SET": bool(os.environ.get("GEMINI_API_KEY")),
            "PYTHON_ENV": os.environ.get("PYTHON_ENV"),
        },
        "memory_info": _mem_info,
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
    print("[OCR] REQUEST RECEIVED")
    if 'bill' not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    file = request.files["bill"]
    print("[OCR] FILE RECEIVED:", file.filename)

    try:
        print("[OCR] ANALYSIS STARTED")
        image = Image.open(file)
        text = pytesseract.image_to_string(image)
        units_consumed, bill_amount, billing_period = parse_bill_text(text)
        print("[OCR] ANALYSIS COMPLETED")
        result = {
            "success": True,
            "units_consumed": units_consumed,
            "bill_amount": bill_amount,
            "billing_period": billing_period or "Not detected",
            "ocr_status": "success",
        }
        print("[OCR] RETURNING JSON")
        return jsonify(result)
    except FileNotFoundError as e:
        print(f"[OCR] FileNotFoundError: {e}")
        return jsonify({
            "success": False,
            "error": "File not found",
            "missing_file": str(e),
        }), 500
    except Exception as e:
        print(f"[OCR] Failed ({type(e).__name__}: {e}) — returning demo mode")
        return jsonify({
            "success": True,
            "ocr_status": "demo",
        })
# ==========================
# ROOFTOP ANALYSIS API
# ==========================

@app.route('/analyze-rooftop', methods=['POST'])
def analyze_rooftop_endpoint():
    print("[rooftop] REQUEST RECEIVED")
    try:
        try:
            from rooftop_analysis import analyze_rooftop
            print("[rooftop] MODEL LOADED (rooftop_analysis module imported)")
        except FileNotFoundError as e:
            print("[rooftop] FileNotFoundError during module import:", str(e))
            return jsonify({
                "success": False,
                "error": "File not found",
                "missing_file": str(e),
            }), 503
        except Exception as e:
            print("[rooftop] Module import failed:", type(e).__name__, str(e))
            return jsonify({'success': False, 'error': 'Analysis module unavailable: ' + str(e)}), 503

        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file provided'}), 400

        print("[rooftop] FILES RECEIVED:", request.files['image'].filename)
        print("[rooftop] ANALYSIS STARTED")
        result = analyze_rooftop(request.files['image'])
        print("[rooftop] ANALYSIS COMPLETED")

        if not isinstance(result, dict):
            print("[rooftop] analyze_rooftop() returned non-dict:", type(result).__name__, repr(result))
            return jsonify({'success': False, 'error': 'Analysis returned unexpected result type'}), 500

        print(
            "[rooftop] RESULT"
            " | success=" + str(result.get('success')) +
            " | error=" + repr(result.get('error')) +
            " | debug=" + repr(result.get('debug'))
        )
        print("[rooftop] RETURNING JSON")
        return jsonify(_safe_json_value(result))

    except FileNotFoundError as e:
        print("[rooftop] FileNotFoundError:", str(e))
        return jsonify({
            "success": False,
            "error": "File not found",
            "missing_file": str(e),
        }), 500
    except Exception as e:
        import traceback
        print("[rooftop] ENDPOINT EXCEPTION:", type(e).__name__, str(e))
        traceback.print_exc()
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
    return jsonify({
        "status": "ok",
        "service": "Helia AI Backend"
    })

# ==========================
# SOLAR PREDICTION API
# ==========================

@app.route("/predict-solar", methods=["POST"])
def predict_solar():

    try:
        print("[predict-solar] REQUEST RECEIVED")
        data = request.get_json(force=True, silent=True)

        if data is None:
            print("[predict] ERROR: No valid JSON body")
            return jsonify({"error": "Request body must be valid JSON."}), 400

        print("[predict-solar] REQUEST:", data)
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

        safe_result = _safe_json_value(result)
        print("[predict-solar] RETURNING JSON (200)")
        return jsonify(safe_result)

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
    "You are Helia, the friendly solar assistant at HelioSense AI — "
    "a platform helping Indian households and businesses plan and switch to solar.\n\n"

    "PERSONALITY:\n"
    "- Friendly, conversational, helpful, and human-like\n"
    "- Sound like a real person chatting, not a textbook or a corporate manual\n"
    "- Be warm, engaging, and keep things interactive\n\n"

    "RESPONSE LENGTH — THIS IS THE MOST IMPORTANT RULE:\n"
    "- DEFAULT: 1–2 sentences only. Always.\n"
    "- Only give a longer response when the user explicitly asks for detail using phrases like:\n"
    "  'explain in detail', 'tell me more', 'detailed analysis', 'full explanation', "
    "'technical explanation', 'elaborate', 'go deeper'\n"
    "- For greetings, farewells, thanks, and casual chat: always reply in 1 sentence\n"
    "- Never write walls of text unless asked\n\n"

    "VARIETY:\n"
    "- Never start two responses in a row with the same opening word or phrase\n"
    "- Vary your greetings and tone naturally\n\n"

    "WHAT NEVER TO SAY:\n"
    "- Never say 'From the knowledge base', 'According to the document', "
    "'The uploaded file states', 'retrieved context', or reference any source files\n"
    "- Never fabricate numbers. If data is not available, say so in one sentence and move on\n\n"

    "HOW TO USE THE USER'S DATA:\n"
    "- When prediction, rooftop, or ROI data is provided, reference those real numbers naturally\n"
    "- Example: say 'Your payback period is 4.8 years' not 'A solar system may pay back in...'\n\n"

    "YOUR AREAS OF EXPERTISE:\n"
    "- Solar system sizing, panel count, capacity, and performance\n"
    "- Rooftop analysis: area, obstructions, shading, suitability\n"
    "- Financial planning: installation cost, ROI, payback period, annual savings\n"
    "- Net metering and grid-tied solar systems\n"
    "- Indian government schemes: PM Surya Ghar, MNRE subsidies, DISCOM regulations\n"
    "- Electricity bill analysis and consumption-based sizing\n\n"

    "Use ₹ for currency. Be concise, warm, and genuinely helpful."
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
    """Call Gemini via the google-genai SDK. Returns None if key is missing or call fails."""
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        print("[helia] _gemini_answer: no API key — skipping Gemini")
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # ── Build context block from available user data ──────────────────────
        ctx_sections = []
        if chunks:
            kb = '\n'.join(c['chunk'] for c in chunks)
            ctx_sections.append(
                "BACKGROUND INFO (internal — do not cite or mention the source; "
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
        full_msg = f"{context_block}\n\nQuestion: {question}" if context_block else question

        # ── Build contents list: history + current message ────────────────────
        # The new SDK takes an explicit contents list instead of a chat session.
        # History must strictly alternate user → model, starting with user.
        contents = []
        expected = 'user'
        for msg in (history or [])[-10:]:
            role = msg.get('role', '')
            text = (msg.get('text') or '').strip()
            gemini_role = 'user' if role == 'user' else 'model'
            if gemini_role != expected or not text:
                continue
            contents.append(types.Content(
                role=gemini_role,
                parts=[types.Part(text=text)],
            ))
            expected = 'model' if expected == 'user' else 'user'
        # Current question always appended as the final user turn
        contents.append(types.Content(
            role='user',
            parts=[types.Part(text=full_msg)],
        ))

        resp = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.5,
                max_output_tokens=500,
                # gemini-2.5-flash is a thinking model; budget=0 disables the
                # internal reasoning step so it returns a direct text response.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if not resp.text:
            print(f"[helia] Gemini returned empty text | model={_GEMINI_MODEL}")
            return None
        return resp.text.strip()

    except Exception as exc:
        try:
            from google import genai as _g
            _sdk_ver = getattr(_g, "__version__", "unknown")
        except Exception:
            _sdk_ver = "unknown"
        print(
            f"[helia] Gemini Exception Type:    {type(exc).__name__}\n"
            f"[helia] Gemini Exception Message: {exc}\n"
            f"[helia] Model Used:               {_GEMINI_MODEL}\n"
            f"[helia] SDK Version:              google-genai {_sdk_ver}\n"
            f"[helia] API Key Present:          {bool(api_key)}"
        )
        app.logger.warning('Gemini error (%s %s): %s', _GEMINI_MODEL, type(exc).__name__, exc)
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