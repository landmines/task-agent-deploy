from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
from pathlib import Path
import traceback
import re
from datetime import datetime, timezone as tz

UTC = tz.utc

from agent_runner import run_agent, finalize_task_execution
from context_manager import load_memory, summarize_memory, save_memory, record_last_result
from task_executor import execute_task, restore_from_backup
from drive_uploader import download_log_by_task_id  # ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ Required for Drive fallback

app = Flask(__name__)
CORS(app)

def write_render_log(message):
    try:
        log_path = os.path.join(os.getcwd(), "logs", "render.log")
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"ÃƒÂ¢Ã…Â¡ ÃƒÂ¯Ã‚Â¸Ã‚Â Failed to write to render.log: {e}")


@app.route("/")
def index():
    return "ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ Agent is running."

@app.route("/run", methods=["POST"])
def run():
    try:
        data = request.get_json()
        print("ÃƒÂ°Ã…Â¸Ã…Â¸Ã‚Â¢ /run received:", data)
        result = run_agent(data)
        print("ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ run_agent result:", result)
        write_render_log(f"Task received: {data}")

        task_id = result.get("taskId") or result.get("result", {}).get("taskId")
        result["taskId"] = task_id
        #Removed redundant taskId and timestamp fields
        if "timestamp" not in result:
            result["timestamp"] = datetime.now(UTC).isoformat()

        return jsonify(result)
    except Exception as e:
        print("ÃƒÂ¢Ã‚ÂÃ…â€™ /run error:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route("/latest", methods=["GET"])
def latest():
    try:
        logs_dir = os.path.join(os.getcwd(), "logs")
        if not os.path.exists(logs_dir):
            return jsonify({"error": "No logs directory found"}), 404

        log_files = sorted(
            [f for f in Path(logs_dir).glob("log-*.json") if f.is_file()],
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )

        if not log_files:
            return jsonify({"error": "No log files found"}), 404

        latest_log_path = log_files[0]
        print(f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã¢â‚¬Å¾ Latest log selected: {latest_log_path}")

        with open(latest_log_path, "r") as f:
            log_data = json.load(f)

        return jsonify(log_data)
    except Exception as e:
        return jsonify({"error": f"Failed to load latest log: {e}"}), 500

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
        logs_dir = os.path.join(os.getcwd(), "logs")
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, exist_ok=True)
            print(f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â Created logs directory at: {logs_dir}")

        log_path = os.path.join(logs_dir, "render.log")
        if not os.path.exists(log_path):
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
        print("ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â Received confirm POST:", data)
        task_id = data.get("taskId")
        approve = data.get("confirm")

        if not task_id or approve is None:
            return jsonify({"error": "Missing taskId or confirm field"}), 400

        from werkzeug.serving import WSGIRequestHandler
        WSGIRequestHandler.timeout = 30

        try:
            if task_id:
                task_id = re.sub(r'[:\./\+T]', '_', task_id)
                task_id = task_id.split('_')[0] if '_' in task_id else task_id

            task_id_variations = [
                task_id,
                task_id.replace('T', '_'),
                task_id.replace('+00:00', ''),
                task_id.replace('+00_00', '')
            ]

            logs_dir = os.path.join(os.getcwd(), "logs")
            os.makedirs(logs_dir, exist_ok=True)

            clean_id = task_id.replace('log-', '')
            timestamp_formats = [f"log-{v}.json" for v in task_id_variations]
            timestamp_formats.extend([
                f"log-*{clean_id}*.json",
                f"log-*{clean_id.split('T')[0]}*.json"
            ])
            print("ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â Trying timestamp formats:", timestamp_formats)

            log_file = os.path.join(logs_dir, f"log-{task_id}.json")
            if os.path.exists(log_file):
                matching_files = [Path(log_file)]
            else:
                matching_files = []
                for pattern in timestamp_formats:
                    matches = list(Path(logs_dir).glob(pattern))
                    if matches:
                        print(f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â Found logs matching {pattern}:", [f.name for f in matches])
                        matching_files.extend(matches)

                if len(matching_files) > 1:
                    matching_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    print(f"ÃƒÂ¢Ã…Â¡ ÃƒÂ¯Ã‚Â¸Ã‚Â Multiple matches found, using most recent: {matching_files[0].name}")

                if not matching_files:
                    matching_files = [f for f in Path(logs_dir).glob("log*.json")
                                      if any(part in f.name for part in [
                                          task_id,
                                          task_id.replace('+00:00', ''),
                                          task_id.replace(':', '_').replace('.', '_')
                                      ])]

            log_data = None
            if matching_files:
                print(f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â Found local log file: {matching_files[0]}")
                with open(matching_files[0], "r") as f:
                    log_data = json.load(f)
            else:
                print(f"ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â No local log found for {task_id}, searching on Drive...")
                try:
                    log_data = download_log_by_task_id(task_id)
                    if log_data is None:
                        return jsonify({
                            "error": "Failed to retrieve log data",
                            "task_id": task_id,
                            "suggestion": "Check if the task ID is correct"
                        }), 404
                except TimeoutError:
                    return jsonify({
                        "error": "Drive operation timed out",
                        "suggestion": "Try again in a few moments"
                    }), 408
                except Exception as e:
                    return jsonify({
                        "error": str(e),
                        "type": "log_retrieval_error",
                        "suggestion": "Check system logs for details"
                    }), 500

            try:
                if approve is False:
                    print("ÃƒÂ¢Ã‚ÂÃ…â€™ Task rejected by user")
                    result = {"success": False, "message": "Task rejected by user"}
                    log_data["rejected"] = True
                    finalize_task_execution("rejected", log_data)
                    return jsonify({"message": "ÃƒÂ¢Ã‚ÂÃ…â€™ Task rejected and logged."})

                log_data["confirmationNeeded"] = False
                plan_to_execute = log_data.get("executionPlanned") or log_data.get("execution")

                if not plan_to_execute:
                    return jsonify({"error": "No execution plan found"}), 400

                if plan_to_execute.get("confirmationNeeded"):
                    plan_to_execute.pop("confirmationNeeded", None)

                result = execute_task(plan_to_execute)
                log_data["executionResult"] = result
                write_render_log(f"Task confirmed: {task_id} | success: {result.get('success')}")
                log_data.setdefault("logs", []).append({"execution": result})
                finalize_task_execution("confirmed", log_data)

                updated_path = matching_files[0] if matching_files else os.path.join(logs_dir, f"log-{task_id}.json")
                with open(updated_path, "w") as f:
                    json.dump(log_data, f, indent=2)

                memory = load_memory()
                record_last_result(memory, plan_to_execute, result)
                return jsonify({
                    "message": "ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ Task confirmed and executed.",
                    "result": result,
                    "success": True
                })

            except Exception as e:
                error_msg = f"Execution failed: {str(e)}"
                result = {"success": False, "error": error_msg}
                log_data["executionResult"] = result
                write_render_log(f"Task confirmed: {task_id} | success: {result.get('success')}")
                log_data.setdefault("logs", []).append({"executionError": result})
                finalize_task_execution("failed", log_data)
                return jsonify({"error": error_msg}), 500


        except Exception as e:
            error_msg = f"Error during log processing or task execution: {str(e)}"
            print(f"ÃƒÂ¢Ã‚ÂÃ…â€™ {error_msg}\n{traceback.format_exc()}")
            return jsonify({"error": error_msg}), 500

    except Exception as e:
        error_msg = f"Confirm handler failed: {str(e)}"
        print("ÃƒÂ¢Ã‚ÂÃ…â€™ /confirm handler error:", traceback.format_exc())
        return jsonify({
            "error": error_msg,
            "success": False,
            "details": traceback.format_exc()
        }), 500

@app.route("/rollback/<task_id>", methods=["POST"])
def rollback_task(task_id):
    try:
        logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(logs_dir, exist_ok=True)
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



@app.route("/memory", methods=["GET"])
def memory():
    try:
        memory = load_memory()
        return jsonify(memory)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000, debug=True)