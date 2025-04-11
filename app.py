# app.py
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
        print("🟢 /run received:", data)
        result = run_agent(data)
        print("✅ run_agent result:", result)

        task_id = result.get("timestamp", "").replace(":", "_").replace(".", "_")
        result["taskId"] = task_id

        return jsonify(result)
    except Exception as e:
        import traceback
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
    task_id = last.get("timestamp", "").replace(":", "_").replace(".", "_")
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
        from drive_uploader import list_recent_logs, download_drive_log_file

        data = request.get_json()
        task_id = data.get("taskId")
        approve = data.get("confirm")

        if not task_id or approve is None:
            return jsonify({"error": "Missing taskId or confirm field"}), 400

        logs_dir = os.path.join(os.getcwd(), "logs")
        local_logs = list(Path(logs_dir).glob("log*.json"))

        # STEP 1A – Search local logs
        matching_files = [f for f in local_logs if task_id in f.name]

        log_data = None
        log_source = "local"
        log_path = None

        if matching_files:
            log_path = matching_files[0]
            with open(log_path, "r") as f:
                log_data = json.load(f)
        else:
            # STEP 1B – Fallback: Search Drive
            recent_ids = list_recent_logs(limit=10)
            for file_id in recent_ids:
                drive_data = download_drive_log_file(file_id)
                embedded_id = drive_data.get("timestamp", "").replace(":", "_").replace(".", "_")
                if task_id == embedded_id:
                    log_data = drive_data
                    log_source = "drive"
                    log_path = os.path.join(logs_dir, f"log-{task_id}.json")
                    break

        if not log_data:
            return jsonify({"error": f"No matching log found for ID: {task_id}"}), 404

        # Handle rejection first
        if not approve:
            log_data["rejected"] = True
            if log_source == "drive":
                os.makedirs(logs_dir, exist_ok=True)
                with open(log_path, "w") as f:
                    json.dump(log_data, f, indent=2)
            else:
                with open(log_path, "w") as f:
                    json.dump(log_data, f, indent=2)

            finalize_task_execution("rejected", log_data)
            return jsonify({"message": "❌ Task rejected and logged."})

        # Proceed with confirmation execution
        log_data["confirmationNeeded"] = False
        try:
            result = execute_task(log_data.get("execution"))
            log_data["executionResult"] = result
            log_data.setdefault("logs", []).append({"execution": result})
        except Exception as e:
            result = {"success": False, "error": f"Execution failed: {str(e)}"}
            log_data["executionResult"] = result
            log_data.setdefault("logs", []).append({"executionError": result})

        # Save updated log locally regardless of source
        os.makedirs(logs_dir, exist_ok=True)
        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2)

        finalize_task_execution("confirmed")

        return jsonify({
            "message": f"✅ Task confirmed and executed from: {log_source} log.",
            "result": result,
            "success": True
        })

    except Exception as e:
        import traceback
        print("❌ /confirm error:", traceback.format_exc())
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