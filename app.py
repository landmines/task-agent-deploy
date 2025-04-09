import sys
import os
import json
import glob
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from agent_runner import run_agent
from confirm_handler import confirm_task
from drive_uploader import list_recent_drive_logs, download_drive_log_file

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

@app.route("/confirm_latest", methods=["POST"])
def confirm_latest():
    logs_dir = os.path.join(os.getcwd(), "logs")
    log_files = sorted(glob.glob(os.path.join(logs_dir, "log-*.json")), reverse=True)

    for file in log_files:
        try:
            task_id = os.path.basename(file).split(".")[0].replace("log-no-", "").replace("/", "").strip()
            result = confirm_task(task_id)
            return jsonify({
                "taskId": task_id,
                "message": f"✅ Confirmed latest task: {task_id}",
                "result": result
            })
        except Exception as e:
            print(f"Error in confirm_latest: {e}")
            return jsonify({"success": False, "error": str(e)})

    return jsonify({"success": False, "error": "No valid logs found to confirm."})

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
    log_files = sorted(
        glob.glob(os.path.join(logs_dir, "log-*.json")),
        key=os.path.getmtime,
        reverse=True
    )

    for file in log_files:
        try:
            print(f"Checking file: {file}")
            with open(file) as f:
                content = json.load(f)
                print("Loaded content keys:", list(content.keys()))
                if isinstance(content, dict) and ("taskReceived" in content or "executionPlanned" in content):
                    print(f"✅ Valid latest log found: {file}")
                    return jsonify({
                        "filename": os.path.basename(file),
                        "content": content
                    })
        except Exception as e:
            print(f"❌ Error reading {file}: {e}")

    print("❌ No valid logs found in /latest")
    return jsonify({
        "error": "No valid logs found",
        "content": None
    })

@app.route("/logs_from_drive", methods=["GET"])
def logs_from_drive():
    try:
        recent_file_ids = list_recent_drive_logs(limit=5)
        logs = []

        for file_id in recent_file_ids:
            content = download_drive_log_file(file_id)
            logs.append({
                "fileId": file_id,
                "content": content
            })

        return jsonify(logs)
    except Exception as e:
        return jsonify({"error": f"Failed to load logs from Drive: {str(e)}"}), 500

@app.route("/panel")
def serve_panel():
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)