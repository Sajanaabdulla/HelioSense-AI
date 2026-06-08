from flask import Blueprint, jsonify, request

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/ask", methods=["POST"])
def ask():
    return jsonify({
        "answer": "Helia AI working"
    })
