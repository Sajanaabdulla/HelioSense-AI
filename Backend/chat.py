from flask import Blueprint, request, jsonify
import os
from typing import List

chat_bp = Blueprint('chat', __name__)


SYSTEM_PROMPT = (
    "You are Helia AI. A solar energy expert. Use available user prediction and ROI data first."
)


@chat_bp.route('/query', methods=['POST'])
def query():
    data = request.json or {}
    question = data.get('question')
    # For scaffold, return a deterministic reply referencing priorities
    response = {
        'answer': f"(Scaffold) I can help with: {question}. Provide assessment/prediction IDs to include user data.",
        'source': ['prediction', 'roi', 'knowledge_base']
    }
    return jsonify(response)
