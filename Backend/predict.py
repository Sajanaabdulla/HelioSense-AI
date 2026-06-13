# =============================================================================
# HelioSense AI — Solar Prediction & Metrics Engine
# =============================================================================
# Loads solar_model.pkl and climatology.pkl (produced by train_model.py)
# and exposes a single predict() function that returns all derived metrics.
# =============================================================================

import os
import math
import logging
import warnings
import numpy as np
import joblib
from datetime import datetime

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH       = os.path.join(BASE_DIR, "models", "solar_model.pkl")
CLIMATOLOGY_PATH = os.path.join(BASE_DIR, "models", "climatology.pkl")

# Support alternate legacy locations for deployed artifacts
if not os.path.exists(MODEL_PATH):
    MODEL_PATH = os.path.join(BASE_DIR, "solar_model.pkl")
if not os.path.exists(CLIMATOLOGY_PATH):
    CLIMATOLOGY_PATH = os.path.join(BASE_DIR, "climatology.pkl")

# ── Constants ─────────────────────────────────────────────────────────────────
PANEL_WATT         = 550          # W  — panel wattage
PANEL_EFFICIENCY   = 0.195        # 19.5 % average commercial panel
SYSTEM_LOSSES      = 0.80         # 80 % derate (inverter, wiring, soiling)
AVG_DAILY_DEMAND   = 10.0         # kWh/day — baseline Indian household
IRRADIANCE_MAX     = 8.0          # kWh/m²/day — theoretical tropical maximum
MONTHS             = ["Jan","Feb","Mar","Apr","May","Jun",
                       "Jul","Aug","Sep","Oct","Nov","Dec"]

# ── Lazy-load models once ─────────────────────────────────────────────────────
_model       = None
_climatology = None

def _load_models():
    global _model, _climatology
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run train_model.py first.")
        _model = joblib.load(MODEL_PATH)
    if _climatology is None:
        if not os.path.exists(CLIMATOLOGY_PATH):
            raise FileNotFoundError(f"Climatology not found at {CLIMATOLOGY_PATH}. Run train_model.py first.")
        _climatology = joblib.load(CLIMATOLOGY_PATH)

# ── Feature Engineering (mirrors train_model.py) ──────────────────────────────
def _build_features(lat, lon, year, month, day, temperature, humidity, wind_speed):
    month_sin = np.sin(2 * np.pi * month / 12)
    month_cos = np.cos(2 * np.pi * month / 12)
    day_sin   = np.sin(2 * np.pi * day   / 31)
    day_cos   = np.cos(2 * np.pi * day   / 31)
    return np.array([[
        lat, lon, year, month, day,
        temperature, humidity, wind_speed,
        month_sin, month_cos, day_sin, day_cos
    ]])

# ── Nearest climatology lookup ─────────────────────────────────────────────────
def _get_climatology_row(lat, lon, month):
    """
    Find the closest (lat, lon) grid point in the climatology table for a given month.
    Returns a dict with {temperature, humidity, wind_speed}.
    """
    df = _climatology
    monthly = df[df["month"] == month].copy()
    if monthly.empty:
        # Fallback to global mean for that month
        monthly = df.copy()

    distances = np.sqrt(
        (monthly["latitude"]  - lat) ** 2 +
        (monthly["longitude"] - lon) ** 2
    )
    nearest = monthly.loc[distances.idxmin()]
    return {
        "temperature": float(nearest["temperature"]),
        "humidity":    float(nearest["humidity"]),
        "wind_speed":  float(nearest["wind_speed"]),
    }

# ── Cloud coverage proxy ───────────────────────────────────────────────────────
def _estimate_cloud_coverage(humidity, irradiance, max_irradiance=IRRADIANCE_MAX):
    """
    Approximate cloud coverage (0–100 %) from humidity and irradiance attenuation.
    - High humidity + low irradiance → more cloud.
    """
    irr_ratio   = max(0.0, 1.0 - (irradiance / max_irradiance))
    humidity_n  = min(1.0, max(0.0, humidity / 100.0))
    raw         = 0.5 * irr_ratio + 0.5 * humidity_n
    return round(float(np.clip(raw * 100, 5, 95)), 1)

# ── Core per-point prediction ──────────────────────────────────────────────────
def _predict_irradiance(lat, lon, year, month, day, temperature, humidity, wind_speed):
    X    = _build_features(lat, lon, year, month, day, temperature, humidity, wind_speed)
    pred = float(_model.predict(X)[0])
    if not math.isfinite(pred):
        logger.warning(
            'model returned non-finite value %r (lat=%s lon=%s month=%s) — clamping to 0.0',
            pred, lat, lon, month,
        )
        return 0.0
    return max(0.0, pred)

# ── Confidence score ───────────────────────────────────────────────────────────
def _confidence_score(irradiance, humidity, lat):
    """
    Heuristic confidence (0–100):
    - Strong irradiance → higher confidence in prediction reliability
    - High humidity → mildly reduces confidence (cloud uncertainty)
    - Tropical latitudes (equatorial belt) → better training coverage
    """
    base   = min(100, (irradiance / IRRADIANCE_MAX) * 100)
    hum_p  = max(0, (100 - humidity) / 100) * 10   # up to +10 if dry
    lat_p  = max(0, (1 - abs(lat - 15) / 40)) * 10  # peak near 15°N (India)
    score  = int(np.clip(base + hum_p + lat_p, 30, 99))
    return score

# ── Suitability classification ─────────────────────────────────────────────────
def _classify_suitability(score):
    if score >= 80:
        return "Excellent", "Highly suitable for rooftop solar installation. Excellent ROI expected."
    elif score >= 60:
        return "Good",      "Good solar potential. Rooftop installation is financially viable."
    elif score >= 40:
        return "Moderate",  "Moderate solar potential. System performance will vary seasonally."
    else:
        return "Poor",      "Low solar potential. Solar installation may not be cost-effective."

# ── Main public API ────────────────────────────────────────────────────────────
def predict(
    latitude:        float,
    longitude:       float,
    temperature:     float,
    humidity:        float,
    wind_speed:      float,
    date:            datetime | None = None,
    cloud_cover_pct: float | None = None,
) -> dict:
    """
    Predict all solar metrics for a given location and current weather.

    Parameters
    ----------
    latitude        : float  — decimal degrees
    longitude       : float  — decimal degrees
    temperature     : float  — °C
    humidity        : float  — % (0–100)
    wind_speed      : float  — m/s
    date            : datetime (optional) — defaults to today
    cloud_cover_pct : float (optional) — cloud cover 0–100 from OWM clouds.all.
                      When provided, a Kasten–Young (1989) empirical cloud-
                      attenuation correction is applied post-prediction.
                      This is more reliable than the humidity-derived proxy
                      used internally when this value is absent, but still an
                      approximation — actual pyranometer measurements would be
                      needed for survey-grade irradiance values.

    Returns
    -------
    dict with all solar KPIs, monthly breakdowns, and suitability metadata.
    """
    _load_models()

    if date is None:
        date = datetime.today()

    year  = date.year
    month = date.month
    day   = date.day

    # ── Current-day irradiance ────────────────────────────────────────────────
    irradiance = _predict_irradiance(
        latitude, longitude, year, month, day,
        temperature, humidity, wind_speed
    )
    raw_irradiance = irradiance   # save RF output before any post-model correction

    # ── Cloud-cover correction ────────────────────────────────────────────────
    # The RF model was trained on historical irradiance that already includes
    # all weather states (humidity is a training feature and acts as a cloudiness
    # proxy for India). Applying the Kasten-Young instantaneous formula to a
    # daily-average model prediction double-counts cloud effects: at 100% OWM
    # cloud cover the original formula produced Kt=0.25, reducing a correct
    # 4.86 kWh/m²/day prediction to 1.21 — physically wrong for a daily average.
    #
    # The correction is now capped so that even a fully overcast report can reduce
    # the daily average by at most 30 % (Kt_min=0.70), which is consistent with
    # real NSRDB/Solargis data for tropical overcast days vs clear-sky days.
    cloud_correction_factor = None
    if cloud_cover_pct is not None:
        c  = float(np.clip(cloud_cover_pct, 0.0, 100.0))
        # Gentle linear scale: 0 % cloud → Kt=1.00, 100 % cloud → Kt=0.70
        Kt = float(np.clip(1.0 - 0.30 * (c / 100.0), 0.70, 1.0))
        irradiance = irradiance * Kt
        cloud_correction_factor = round(Kt, 4)
        logger.debug(
            'predict: cloud correction Kt=%.4f applied (cloud_cover_pct=%.1f)',
            Kt, c,
        )

    # Guard: irradiance must be finite before any derived calculation.
    if not math.isfinite(irradiance):
        logger.warning(
            'predict: irradiance is %r after all corrections — clamping to 0.0', irradiance
        )
        irradiance = 0.0

    # ── Step trace — printed on every call so the drop is visible in the terminal
    print(
        f"[predict] STEP-TRACE"
        f" | lat={latitude} lon={longitude}"
        f" | raw_RF={raw_irradiance:.4f}"
        f" | cloud_cover_pct={cloud_cover_pct}"
        f" | Kt={cloud_correction_factor}"
        f" | final_irradiance={irradiance:.4f}"
    )

    # ── Derived KPIs ──────────────────────────────────────────────────────────
    # peak_sun_hours IS irradiance — there is no separate formula.
    # Any cloud correction applied above flows directly into peak_sun_hours.
    peak_sun_hours = round(irradiance, 2)

    # Solar Potential Score (0–100)
    potential_score = round(min(100.0, (irradiance / IRRADIANCE_MAX) * 100), 1)

    print(
        f"[predict] STEP-TRACE"
        f" | peak_sun_hours={peak_sun_hours}"
        f" | potential_score={potential_score}"
        f" | (IRRADIANCE_MAX used={IRRADIANCE_MAX})"
    )

    # Recommended capacity (kW) — sized to cover avg daily demand
    # E = Capacity_kW × PSH × system_losses
    if peak_sun_hours > 0:
        recommended_capacity = round(AVG_DAILY_DEMAND / (peak_sun_hours * SYSTEM_LOSSES), 2)
    else:
        recommended_capacity = 0.0

    # Panel count (ceil to nearest int)
    panel_count = int(np.ceil((recommended_capacity * 1000) / PANEL_WATT))

    # Annual energy projection from climatology monthly averages
    # Will be computed below after monthly loop — placeholder for now

    # ── Monthly forecast from climatology ─────────────────────────────────────
    monthly_generation   = {}
    monthly_cloud        = {}
    monthly_irradiance   = {}

    for m_idx, m_name in enumerate(MONTHS, start=1):
        clim = _get_climatology_row(latitude, longitude, m_idx)
        import calendar
        days_in_month = calendar.monthrange(year, m_idx)[1]

        daily_irr = _predict_irradiance(
            latitude, longitude, year, m_idx, 15,          # representative mid-month day
            clim["temperature"], clim["humidity"], clim["wind_speed"]
        )

        # Monthly generation (kWh) = capacity × PSH × losses × days
        monthly_kwh = round(
            recommended_capacity * daily_irr * SYSTEM_LOSSES * days_in_month, 1
        )
        cloud_pct = _estimate_cloud_coverage(clim["humidity"], daily_irr)

        monthly_generation[m_name]  = monthly_kwh
        monthly_cloud[m_name]       = cloud_pct
        monthly_irradiance[m_name]  = round(daily_irr, 3)

    # ── Annual projection & coverage ──────────────────────────────────────────
    annual_projection = round(sum(monthly_generation.values()), 1)   # kWh/year
    annual_demand     = AVG_DAILY_DEMAND * 365
    energy_coverage   = round(min(100.0, (annual_projection / annual_demand) * 100), 1)

    # ── Confidence & suitability ──────────────────────────────────────────────
    confidence              = _confidence_score(irradiance, humidity, latitude)
    suitability, recommendation = _classify_suitability(potential_score)

    return {
        # Core metrics
        "predicted_irradiance"  : round(irradiance, 4),
        "raw_model_prediction"  : round(raw_irradiance, 4),  # RF output before cloud correction
        "potential_score"       : round(potential_score, 1),
        "peak_sun_hours"        : peak_sun_hours,
        "annual_projection"     : annual_projection,
        "recommended_capacity"  : recommended_capacity,
        "panel_count"           : panel_count,
        "energy_coverage"       : energy_coverage,

        # Monthly breakdowns
        "monthly_generation"    : monthly_generation,
        "monthly_cloud_coverage": monthly_cloud,
        "monthly_irradiance"    : monthly_irradiance,

        # Metadata
        "confidence"            : confidence,
        "suitability"           : suitability,
        "recommendation"        : recommendation,

        # Echo inputs and any post-model corrections applied
        "inputs": {
            "latitude"                : latitude,
            "longitude"               : longitude,
            "temperature"             : temperature,
            "humidity"                : humidity,
            "wind_speed"              : wind_speed,
            "date"                    : date.strftime("%Y-%m-%d"),
            "cloud_cover_pct"         : cloud_cover_pct,
            "cloud_correction_factor" : cloud_correction_factor,
        }
    }


# ── CLI diagnostic ────────────────────────────────────────────────────────────
# Run:  python Backend/predict.py
# Shows step-by-step values for three Kerala cities at three cloud-cover levels.
if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.WARNING)

    CITIES = [
        # name                    lat     lon    temp   hum   ws
        ("Kollam",               8.88,  76.60,  31.0,  85.0, 3.0),
        ("Kozhikode",           11.25,  75.78,  30.0,  80.0, 4.0),
        ("Thiruvananthapuram",   8.52,  76.94,  31.0,  83.0, 3.5),
    ]

    CLOUD_LEVELS = [
        ("no cloud data (cloud_cover_pct=None)",  None),
        ("cloud 0 % (clear sky)",                  0.0),
        ("cloud 50 % (partly cloudy)",            50.0),
        ("cloud 75 % (monsoon typical)",          75.0),
        ("cloud 100 % (fully overcast)",         100.0),
    ]

    SEP = "-" * 78

    for cloud_label, cloud_pct in CLOUD_LEVELS:
        print(f"\n{'='*78}")
        print(f"  {cloud_label}")
        print(f"{'='*78}")
        print(f"  {'City':<26} {'raw_RF':>8} {'Kt':>6} {'final_irr':>10} {'PSH':>6} {'score':>6}")
        print(SEP)

        for name, lat, lon, temp, hum, ws in CITIES:
            r = predict(
                latitude        = lat,
                longitude       = lon,
                temperature     = temp,
                humidity        = hum,
                wind_speed      = ws,
                cloud_cover_pct = cloud_pct,
            )
            raw   = r["raw_model_prediction"]
            Kt    = r["inputs"]["cloud_correction_factor"]
            final = r["predicted_irradiance"]
            psh   = r["peak_sun_hours"]
            score = r["potential_score"]
            kt_str = f"{Kt:.4f}" if Kt is not None else "  N/A"
            print(f"  {name:<26} {raw:>8.4f} {kt_str:>6} {final:>10.4f} {psh:>6.2f} {score:>6.1f}")

    print(f"\n{SEP}")
    print("  KEY FORMULA:")
    print("    Kt (cloud correction) = clip(1 - 0.30 * (cloud_pct/100),  min=0.70, max=1.0)")
    print("    final_irradiance      = raw_RF * Kt")
    print("    peak_sun_hours        = round(final_irradiance, 2)   <-- same number, no separate formula")
    print("    potential_score       = round(min(100, final_irradiance / 8.0 * 100), 1)")
    print(f"    IRRADIANCE_MAX used   = {IRRADIANCE_MAX}  kWh/m²/day")
    print(SEP)
