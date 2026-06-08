from flask import Blueprint, request, jsonify
assessment_bp = Blueprint('assessment', __name__)

_assessments = {}
_next = 1


@assessment_bp.route('/create', methods=['POST'])
def create_assessment():
    global _next
    data = request.json or {}
    aid = _next
    _next += 1
    data['id'] = aid
    _assessments[aid] = data
    return jsonify({'status': 'ok', 'assessment_id': aid}), 201


@assessment_bp.route('/get/<int:aid>', methods=['GET'])
def get_assessment(aid):
    a = _assessments.get(aid)
    if not a:
        return jsonify({'error': 'not found'}), 404
    return jsonify(a)
