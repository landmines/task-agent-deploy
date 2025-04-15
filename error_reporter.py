import os, json, glob
LOGS_DIR = "logs"
REPORT_FILE = "builder_error_report.txt"
def load_latest_failed_log():
    log_files = sorted(glob.glob(os.path.join(LOGS_DIR, "log-*.json")), reverse=True)
    for path in log_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not data.get("result", {}).get("success", True):
                return path, data
        except Exception:
            continue
    return None, None

def generate_error_report():
    path, data = load_latest_failed_log()
    if not data:
        return "✅ No failed task found in recent logs."
    result = data.get("result", {})
    task = data.get("task", {})
    error_msg = result.get("message") or result.get("error") or "Unknown error"
    timestamp = data.get("timestamp", "unknown")
    report = f"""
❌ Builder Agent Error Report
----------------------------
Task:      {task.get('intent', 'unknown')}
Filename:  {task.get('filename', 'unknown')}
Error:     {error_msg}
Timestamp: {timestamp}
Log file:  {os.path.basename(path)}
""".strip()
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report + "
")
    return report

if __name__ == "__main__":
    print(generate_error_report())