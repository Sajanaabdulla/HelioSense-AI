from flask import Blueprint, request, jsonify
roi_bp = Blueprint('roi', __name__)


@roi_bp.route('/calculate', methods=['POST'])
def calculate_roi():
    data = request.json or {}
    system_cost = float(data.get('system_cost', 10000))
    electricity_tariff = float(data.get('electricity_tariff', 0.12))
    subsidy = float(data.get('subsidy', 0))
    panel_eff = float(data.get('panel_efficiency', 0.18))
    annual_generation = float(data.get('annual_generation_kwh', 1000))

    adjusted_cost = system_cost - subsidy

    annual_savings = annual_generation * electricity_tariff
    monthly_savings = annual_savings / 12.0

    payback_years = adjusted_cost / annual_savings if annual_savings > 0 else None

    roi_percent = (annual_savings / adjusted_cost * 100) if adjusted_cost > 0 else None

    lifetime_years = 25
    lifetime_savings = annual_savings * lifetime_years - adjusted_cost

    co2_reduction_kg = annual_generation * 0.5  # rough factor: 0.5 kg CO2 per kWh

    result = {
        'annual_savings': round(annual_savings, 2),
        'monthly_savings': round(monthly_savings, 2),
        'payback_years': round(payback_years, 2) if payback_years else None,
        'roi_percent': round(roi_percent, 2) if roi_percent else None,
        'lifetime_savings': round(lifetime_savings, 2),
        'co2_reduction_kg': round(co2_reduction_kg, 2)
    }
    return jsonify(result)
