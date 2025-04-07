import sys
import os

# Ensure current directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
from flask_cors import CORS

# Import after sys.path is updated
from agent_runner import run_agent

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return "✅ Agent is running!"

@app.route("/run", methods=["POST"])
def run():
    input_data = request.get_json() or {}
    result = run_agent(input_data)
    return jsonify(result)

# This part is ignored on Render, but safe for local testing
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
