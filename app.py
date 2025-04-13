from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
from pathlib import Path
import traceback

from agent_runner import run_agent, finalize_task_execution
from context_manager import load_memory, summarize_memory, save_memory, record_last_result
from task_executor import execute_task
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

@app.route("/run_next", methods=["POST"])
def run_next():
    try:
        memory = load_memory()
        queue = memory.get("next_steps", [])
        if not queue:
            return jsonify({"error": "⚠️ No queued tasks in memory."}), 400

        next_item = queue.pop(0)
        task = next_item.get("step") if isinstance(next_item, dict) and "step" in next_item else next_item
        memory["next_steps"] = queue
        save_memory(memory)

        try:
            result = run_agent(task)
        except Exception as e:
            return jsonify({"error": f"Task execution failed: {str(e)}"}), 500

        return jsonify({
            "message": "✅ Ran next task from memory queue.",
            "task": task,
            "result": result
        })
    except Exception as e:
        return jsonify({"error": f"run_next failed: {e}"}), 500

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
        WSGIRequestHandler.timeout = 30

        # Normalize taskId format comprehensively
        task_id = task_id.replace(":", "_").replace(".", "_").replace("/", "_").replace("+", "_")
        task_id = task_id.split(".")[0]  # Remove microseconds if present
        if not task_id.startswith("log-"):
            task_id = f"log-{task_id}"

        logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(logs_dir, exist_ok=True)

        try:
            # Try multiple timestamp formats for local files
            # Remove any accidental double "log-" prefixes
            clean_id = task_id.replace('log-', '')
            timestamp_formats = [
                f"log-{clean_id}.json",
                f"log-{clean_id.replace('+00:00', '')}.json",
                f"log-{clean_id.replace('+00_00', '')}.json",
                f"log-{clean_id.split('.')[0]}.json",
                f"log-{clean_id.split('T')[0]}*.json"
            ]
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
                    log_data = download_log_by_task_id(task_id)
                    if not log_data:
                        return jsonify({"error": "Timeout while retrieving log from Drive"}), 408
                except Exception as e:
                    print(f"⚠️ Drive search failed: {e}")
                    return jsonify({"error": "Log retrieval failed - timeout or connection error"}), 500

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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)