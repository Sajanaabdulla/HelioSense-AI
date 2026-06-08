from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
import datetime

auth_bp = Blueprint('auth', __name__)

# NOTE: This scaffold uses simple in-memory demo logic for user creation.
users_store = {}


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json or {}
    email = data.get('email')
    if not email:
        return jsonify({'error': 'email required'}), 400
    if email in users_store:
        return jsonify({'error': 'user exists'}), 400
    pw = data.get('password', 'changeme')
    users_store[email] = {
        'name': data.get('name'),
        'email': email,
        'phone': data.get('phone'),
        'location': data.get('location'),
        'password_hash': generate_password_hash(pw)
    }
    return jsonify({'status': 'ok', 'email': email}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get('email')
    pw = data.get('password')
    u = users_store.get(email)
    if not u or not check_password_hash(u['password_hash'], pw):
        return jsonify({'error': 'invalid credentials'}), 401
    token = create_access_token(identity=email, expires_delta=datetime.timedelta(days=7))
    return jsonify({'access_token': token, 'user': {'email': email, 'name': u.get('name')}})
