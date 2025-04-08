# app.py
import sys
import os
import json
import glob
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from agent_runner import run_agent
from confirm_handler import confirm_task

# Ensure current directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, static_folder="static")
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

@app.route("/logs", methods=["GET"])
def logs():
    logs_dir = os.path.join(os.getcwd(), "logs")
    log_files = sorted(glob.glob(os.path.join(logs_dir, "log-*.json")), reverse=True)
    recent_logs = []

    for file in log_files[:5]:
        try:
            with open(file) as f:
                content = json.load(f)
                recent_logs.append({
                    "filename": os.path.basename(file),
                    "content": content
                })
        except Exception as e:
            print(f"Failed to read {file}: {e}")

    return jsonify(recent_logs)

@app.route("/latest", methods=["GET"])
def latest():
    logs_dir = os.path.join(os.getcwd(), "logs")
    log_files = sorted(glob.glob(os.path.join(logs_dir, "log-*.json")), reverse=True)

    for file in log_files:
        try:
            with open(file) as f:
                content = json.load(f)
                return jsonify({ "content": content })  # ✅ Wrap response in 'content'
        except Exception as e:
            print(f"Error reading {file}: {e}")

    return jsonify({ "error": "No valid logs found" })

@app.route("/panel")
def serve_panel():
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
