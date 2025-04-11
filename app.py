from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
from pathlib import Path

from agent_runner import run_agent, finalize_task_execution
from context_manager import load_memory, summarize_memory, save_memory
from task_executor import execute_task

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return "✅ Agent is running."

@app.route("/run", methods=["POST"])
def run():
    try:
        data = request.get_json()
        print("🟢 /run received:", data)  # Log incoming data
        result = run_agent(data)
        print("✅ run_agent result:", result)  # Log result for debug

        # 🟢 PATCH: Extract taskId from the resulting timestamp for confirmations
        task_id = result.get("timestamp", "").replace(":", "_").replace(".", "_")
        result["taskId"] = task_id

        return jsonify(result)
    except Exception as e:
        import traceback
        print("❌ /run error:", traceback.format_exc())  # Full traceback
        return jsonify({"error": str(e)}), 500

@app.route("/run_next", methods=["POST"])
def run_next():
    try:
        memory = load_memory()
        queue = memory.get("next_steps", [])
        if not queue:
            return jsonify({"error": "⚠️ No queued tasks in memory."}), 400

        next_item = queue.pop(0)
        task = next_item.get("step", next_item)
        save_memory(memory)

        result = run_agent(task)
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
    task_id = last.get("timestamp", "").replace(":", "_").replace(".", "_")  # 🌟 PATCH: Provide task ID for confirmation
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

@app.route("/confirm", methods=["POST"])
def confirm():
    try:
        from drive_uploader import download_log_by_task_id  # ✅ NEW: import fallback
        data = request.get_json()
        task_id = data.get("taskId")
        approve = data.get("confirm")

        if not task_id or approve is None:
            return jsonify({"error": "Missing taskId or confirm field"}), 400

        logs_dir = os.path.join(os.getcwd(), "logs")

        # 🔍 PATCH: Match task ID with full flexibility across all known formats
        matching_files = [
            f for f in Path(logs_dir).glob("log*.json")
            if task_id in f.name
        ]

        log_data = None

        if matching_files:
            with open(matching_files[0], "r") as f:
                log_data = json.load(f)
        else:
            # ✅ Fallback: Try to get the log from Google Drive
            log_data = download_log_by_task_id(task_id)
            if not log_data:
                return jsonify({"error": f"No matching log found locally or in Drive for ID: {task_id}"}), 404

        if not approve:
            log_data["rejected"] = True
            finalize_task_execution("rejected", log_data)  # ✅ FIX: Pass task info if rejected
            return jsonify({"message": "❌ Task rejected and logged."})

        log_data["confirmationNeeded"] = False

        try:
            result = execute_task(log_data.get("executionPlanned"))
            log_data["executionResult"] = result
            log_data.setdefault("logs", []).append({"execution": result})
        except Exception as e:
            result = {"success": False, "error": f"Execution failed: {str(e)}"}
            log_data["executionResult"] = result
            log_data.setdefault("logs", []).append({"executionError": result})

        finalize_task_execution("confirmed")

        return jsonify({
            "message": "✅ Task confirmed and executed.",
            "result": result,
            "success": True
        })

    except Exception as e:
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
    app.run(debug=True)