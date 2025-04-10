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
        result = run_agent(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/run_next", methods=["POST"])
def run_next():
    try:
        memory = load_memory()
        queue = memory.get("next_steps", [])
        if not queue:
            return jsonify({"error": "⚠️ No queued tasks in memory."}), 400

        next_task = queue.pop(0)
        save_memory(memory)

        result = run_agent(next_task)
        return jsonify({
            "message": "✅ Ran next task from memory queue.",
            "task": next_task,
            "result": result
        })
    except Exception as e:
        return jsonify({"error": f"run_next failed: {e}"}), 500

@app.route("/latest", methods=["GET"])
def latest():
    logs_dir = os.path.join(os.getcwd(), "logs")
    files = sorted(Path(logs_dir).glob("*.json"), reverse=True)

    for file in files:
        try:
            with open(file, "r") as f:
                content = json.load(f)
            if isinstance(content, dict) and "executionPlanned" in content:
                return jsonify({"file": file.name, "content": content})
        except Exception as e:
            print(f"❌ Error reading {file.name}: {e}")
    return jsonify({"error": "❌ No valid logs found in /latest"})

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
        data = request.get_json()
        task_id = data.get("taskId")
        approve = data.get("confirm")

        if not task_id or approve is None:
            return jsonify({"error": "Missing taskId or confirm field"}), 400

        logs_dir = os.path.join(os.getcwd(), "logs")
        matching_files = [f for f in Path(logs_dir).glob("log-*.json") if task_id in f.name]
        if not matching_files:
            return jsonify({"error": f"No matching log file found for ID: {task_id}"}), 404

        log_file = matching_files[0]

        with open(log_file, "r") as f:
            log_data = json.load(f)

        if not approve:
            log_data["rejected"] = True
            with open(log_file, "w") as f:
                json.dump(log_data, f, indent=2)
            return jsonify({"message": "❌ Task rejected and logged."})

        log_data["confirmationNeeded"] = False

        try:
            result = execute_task(log_data.get("executionPlanned"))
            log_data["executionResult"] = result
            log_data["logs"].append({"execution": result})
        except Exception as e:
            result = {"success": False, "error": f"Execution failed: {str(e)}"}
            log_data["executionResult"] = result
            log_data["logs"].append({"executionError": result})

        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2)

        finalize_task_execution(log_data)

        return jsonify({
            "message": f"✅ Task confirmed and executed from: {log_file.name}",
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