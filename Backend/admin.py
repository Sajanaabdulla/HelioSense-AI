from flask import Blueprint, jsonify
admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/users', methods=['GET'])
def list_users():
    # For scaffold return empty list
    return jsonify({'users': []})
