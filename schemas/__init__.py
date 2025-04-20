import json
import os

# locate this file's directory
_dir = os.path.dirname(__file__)

# load the JSON schema
with open(os.path.join(_dir, "task.schema.json"), encoding="utf‑8") as f:
    TASK_REQUEST_SCHEMA = json.load(f)
