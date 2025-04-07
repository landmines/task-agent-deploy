import os
import sys

# 🔧 Ensure Python can locate modules in current directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from flask import Flask, request, jsonify
from flask_cors import CORS
from agent_runner import run_agent

# 🔥 WSGI-compatible Flask app (Render and Gunicorn expect this exact name)
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

# 💻 Only runs this block during local development (not Render)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
