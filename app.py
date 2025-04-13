from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
from pathlib import Path
import traceback
from datetime import datetime, timezone as tz

UTC = tz.utc

from agent_runner import run_agent, finalize_task_execution
from context_manager import load_memory, summarize_memory, save_memory, record_last_result
from task_executor import execute_task, restore_from_backup
from drive_uploader import download_log_by_task_id  # ✅ Required for Drive fallback

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return "✅ Agent is running."

@app.route("/run", methods=["POST"])
def run():
    try:
        data = request.get_json()
        print("🟢 /run received:", data)
        result = run_agent(data)
        print("✅ run_agent result:", result)

        # Ensure both top-level and nested result have taskId
        task_id = result.get("taskId") or result.get("result", {}).get("taskId")
        result["taskId"] = task_id
        if "result" in result and isinstance(result["result"], dict):
            result["result"]["taskId"] = task_id
        result["timestamp"] = result.get("timestamp")

        return jsonify(result)
    except Exception as e:
        print("❌ /run error:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route("/latest", methods=["GET"])
def get_latest_result():
    memory = load_memory()
    last = memory.get("last_result")
    if not last:
        return jsonify({"message": "No latest result available."}), 200

    task = last.get("task", {})
    task_id = last.get("taskId")

    return jsonify({
        "content": {
            "confirmationNeeded": task.get("confirmationNeeded", False),
            "timestamp": last.get("timestamp"),
            "result": last.get("result"),
            "task": task,
            "intent": last.get("intent"),
            "taskId": task_id
        }
    }), 200

@app.route("/logs_from_drive", methods=["GET"])
def logs_from_drive():
    from drive_uploader import list_recent_logs
    try:
        logs = list_recent_logs(limit=5)
        return jsonify(logs)
    except Exception as e:
        return jsonify({"error": f"Drive fetch failed: {e}"}), 500

@app.route("/logs_snapshot", methods=["GET"])
def logs_snapshot():
    try:
        log_path = os.path.join(os.getcwd(), "render.log")
        if not os.path.exists(log_path):
            # Create empty log file if it doesn't exist
            with open(log_path, "w") as f:
                f.write("Log file initialized\n")
            return jsonify({"success": True, "logs": ["Log file initialized"]})

        with open(log_path, "r") as f:
            lines = f.readlines()[-100:]
        return jsonify({"success": True, "logs": lines})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/confirm", methods=["POST", "OPTIONS"])
def confirm():
    if request.method == "OPTIONS":
        return "", 200

    try:
        data = request.get_json()
        print("🔍 Received confirm POST:", data)
        task_id = data.get("taskId")
        approve = data.get("confirm")

        if not task_id or approve is None:
            return jsonify({"error": "Missing taskId or confirm field"}), 400

        from werkzeug.serving import WSGIRequestHandler
        WSGIRequestHandler.timeout = 120  # Increased timeout

        # Normalize taskId format comprehensively
        task_id = task_id.replace(":", "_").replace(".", "_").replace("/", "_").replace("+", "_").replace("T", "_")
        task_id = task_id.split(".")[0]  # Remove microseconds if present
        task_id = task_id.split("+")[0]  # Remove timezone if present

        # Try variations of the task ID for more flexible matching
        task_id_variations = [
            task_id,
            task_id.replace('T', '_'),
            task_id.replace('+00:00', ''),
            task_id.replace('+00_00', '')
        ]

        logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(logs_dir, exist_ok=True)

        try:
            # Try multiple timestamp formats for local files
            clean_id = task_id.replace('log-', '')
            timestamp_formats = [f"log-{v}.json" for v in task_id_variations]
            timestamp_formats.extend([
                f"log-*{clean_id}*.json",
                f"log-*{clean_id.split('T')[0]}*.json"
            ])
            print(f"🔍 Searching for log files matching patterns: {timestamp_formats}")

            # Direct path attempt first
            log_file = os.path.join(logs_dir, f"log-{task_id}.json")
            if os.path.exists(log_file):
                matching_files = [Path(log_file)]
            else:
                matching_files = []
                for pattern in timestamp_formats:
                    matches = list(Path(logs_dir).glob(pattern))
                    if matches:
                        print(f"📁 Found logs matching {pattern}:", [f.name for f in matches])
                        matching_files.extend(matches)

                if len(matching_files) > 1:
                    matching_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    print(f"⚠️ Multiple matches found, using most recent: {matching_files[0].name}")

                if not matching_files:
                    matching_files = [f for f in Path(logs_dir).glob("log*.json") 
                                    if any(part in f.name for part in [
                                        task_id, 
                                        task_id.replace('+00:00', ''),
                                        task_id.replace(':', '_').replace('.', '_')
                                    ])]

            log_data = None
            if matching_files:
                print(f"📝 Found local log file: {matching_files[0]}")
                with open(matching_files[0], "r") as f:
                    log_data = json.load(f)
            else:
                print(f"🔍 No local log found for {task_id}, searching on Drive...")
                try:
                    from werkzeug.serving import WSGIRequestHandler
                    WSGIRequestHandler.timeout = 120  # Increase timeout for Drive operations
                    log_data = download_log_by_task_id(task_id)

                    if not log_data:
                        return jsonify({"error": "Log not found locally or in Drive"}), 404
                except Exception as e:
                    print(f"⚠️ Error retrieving log: {e}")
                    return jsonify({"error": f"Failed to retrieve log: {str(e)}"}), 500

            if not log_data:
                return jsonify({
                    "error": f"No matching log found for ID: {task_id}",
                    "details": "Checked both local storage and Drive"
                }), 404
        except Exception as e:
            return jsonify({"error": f"Error accessing logs: {str(e)}"}), 500

        if approve is False:
            log_data["rejected"] = True
            finalize_task_execution("rejected", log_data)
            return jsonify({"message": "❌ Task rejected and logged."})

        log_data["confirmationNeeded"] = False
        plan_to_execute = log_data.get("executionPlanned") or log_data.get("execution")

        if plan_to_execute.get("confirmationNeeded"):
            plan_to_execute.pop("confirmationNeeded", None)

        try:
            result = execute_task(plan_to_execute)
            log_data["executionResult"] = result
            log_data.setdefault("logs", []).append({"execution": result})
        except Exception as e:
            result = {"success": False, "error": f"Execution failed: {str(e)}"}
            log_data["executionResult"] = result
            log_data.setdefault("logs", []).append({"executionError": result})

        finalize_task_execution("confirmed")

        updated_path = matching_files[0] if matching_files else os.path.join(logs_dir, f"log-{task_id}.json")
        try:
            with open(updated_path, "w") as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not update local log file: {e}")

        memory = load_memory()
        record_last_result(memory, plan_to_execute, result)

        return jsonify({
            "message": "✅ Task confirmed and executed.",
            "result": result,
            "success": True
        })

    except Exception as e:
        print("❌ /confirm handler error:", traceback.format_exc())
        return jsonify({"error": f"Confirm handler failed: {e}"}), 500

@app.route("/memory", methods=["GET"])
def memory():
    try:
        memory = load_memory()
        return jsonify(memory)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/memory/summary", methods=["GET"])
def memory_summary():
    try:
        memory = load_memory()
        summary = summarize_memory(memory)
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/rollback/<task_id>", methods=["POST"])
def rollback_task(task_id):
    try:
        logs_dir = os.path.join(os.getcwd(), "logs")
        log_file = os.path.join(logs_dir, f"log-{task_id}.json")

        if not os.path.exists(log_file):
            return jsonify({"error": "Task log not found"}), 404

        with open(log_file, "r") as f:
            log_data = json.load(f)

        if "backup" not in log_data.get("result", {}):
            return jsonify({"error": "No backup available for rollback"}), 400

        result = restore_from_backup(log_data["result"]["backup"])

        if result["success"]:
            log_data["rolled_back"] = True
            log_data["rollback_result"] = result
            with open(log_file, "w") as f:
                json.dump(log_data, f, indent=2)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/rollback_last', methods=["POST"])
def rollback_last():
    try:
        memory = load_memory()
        last_result = memory.get("last_result", {})
        if not last_result:
            return jsonify({"error": "No previous task found"}), 404

        result = last_result.get("result", {})
        if "backup" not in result:
            return jsonify({"error": "No backup available for last task"}), 400

        rollback_result = restore_from_backup(result["backup"])

        if rollback_result["success"]:
            memory["last_rollback"] = {
                "task": last_result,
                "timestamp": datetime.now(UTC).isoformat(),
                "result": rollback_result
            }
            save_memory(memory)

        return jsonify(rollback_result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)