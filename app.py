# app.py
import sys
import os

# Ensure current directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
from flask_cors import CORS
from agent_runner import run_agent
from confirm_handler import confirm_task

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

@app.route("/confirm", methods=["POST"])
def confirm():
    data = request.get_json() or {}
    task_id = data.get("taskId", "").replace(":", "_").split(".")[0].replace("/", "").strip()
    confirm_flag = data.get("confirm", False)

    if not task_id or not confirm_flag:
        return jsonify({"success": False, "error": "Missing taskId or confirm=true"})

    result = confirm_task(task_id)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
