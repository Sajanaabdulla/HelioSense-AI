from flask import Blueprint, request, jsonify
import math

prediction_bp = Blueprint('prediction', __name__)


def compute_peak_sun_hours(latitude: float) -> float:
    # Rough heuristic: higher near tropics; clamp between 3 and 6
    base = 4.5 - (abs(latitude) / 90.0) * 1.5
    return max(3.0, min(6.0, base))


@prediction_bp.route('/generate', methods=['POST'])
def generate_prediction():
    data = request.json or {}
    lat = float(data.get('latitude', 0))
    monthly_bill = float(data.get('monthly_bill', 0))
    tariff = float(data.get('tariff', data.get('electricity_tariff', 0.12)))
    roof_area = float(data.get('roof_area', 50))

    psh = compute_peak_sun_hours(lat)

    # Estimate monthly consumption (kWh)
    if tariff > 0:
        monthly_consumption_kwh = monthly_bill / tariff
    else:
        monthly_consumption_kwh = 250

    monthly_gen_per_kw = psh * 30
    recommended_kw = monthly_consumption_kwh / monthly_gen_per_kw if monthly_gen_per_kw > 0 else 0

    # Cap by roof area: assume 6.5 m2 per kW
    max_capacity_by_area = roof_area / 6.5
    recommended_kw = min(recommended_kw, max_capacity_by_area)

    annual_generation = recommended_kw * psh * 365

    solar_score = min(100, max(0, int((psh - 3.0) / 3.0 * 100)))

    recommended_panels = max(1, int(recommended_kw * 1000 / 400))  # assume 400W panels

    result = {
        'solar_score': solar_score,
        'peak_sun_hours': round(psh, 2),
        'annual_generation_kwh': round(annual_generation, 2),
        'recommended_capacity_kw': round(recommended_kw, 2),
        'recommended_panels': recommended_panels,
        'roof_suitability': 'Good' if solar_score > 50 and recommended_kw > 0.5 else 'Marginal'
    }

    return jsonify(result)
