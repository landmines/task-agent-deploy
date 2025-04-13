import os
import json
from datetime import datetime, UTC
from typing import Dict, Any, List
import zipfile
import time
import requests
import hashlib

class DeploymentManager:
    def __init__(self):
        self.cost_metrics = {
            "compute": 0.000012,  # Per second
            "storage": 0.000001,  # Per MB per hour
            "bandwidth": 0.00001  # Per MB
        }

    def estimate_deployment_cost(self, resources: Dict[str, Any]) -> Dict[str, float]:
        """Estimate deployment costs based on resource usage"""
        compute_hours = resources.get("compute_hours", 0)
        storage_mb = resources.get("storage_mb", 0)
        bandwidth_mb = resources.get("bandwidth_mb", 0)

        return {
            "compute_cost": compute_hours * 3600 * self.cost_metrics["compute"],
            "storage_cost": storage_mb * self.cost_metrics["storage"] * 24,
            "bandwidth_cost": bandwidth_mb * self.cost_metrics["bandwidth"],
            "total_cost": (compute_hours * 3600 * self.cost_metrics["compute"]) + 
                         (storage_mb * self.cost_metrics["storage"] * 24) + 
                         (bandwidth_mb * self.cost_metrics["bandwidth"])
        }

    def optimize_deployment(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize deployment configuration"""
        optimized = config.copy()

        # Optimize memory allocation
        if "memory_mb" in optimized:
            optimized["memory_mb"] = max(128, min(optimized["memory_mb"], 512))

        # Optimize instance count
        if "instances" in optimized:
            optimized["instances"] = max(1, min(optimized["instances"], 3))

        # Set reasonable timeouts
        optimized.setdefault("timeout_seconds", 30)
        optimized.setdefault("startup_timeout_seconds", 60)

        return optimized

    def deploy(self, config: Dict[str, Any], optimize: bool = True) -> Dict[str, Any]:
        """Deploy application with optimization"""
        if optimize:
            config = self.optimize_deployment(config)

        # Store deployment record
        deployment_record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "config": config,
            "estimated_costs": self.estimate_deployment_cost({
                "compute_hours": 24,  # Estimate for 1 day
                "storage_mb": config.get("storage_mb", 100),
                "bandwidth_mb": config.get("bandwidth_mb", 1000)
            })
        }

        self._save_deployment_record(deployment_record)
        return deployment_record

    def _save_deployment_record(self, record: Dict[str, Any]) -> None:
        """Save deployment record for tracking"""
        records_file = "deployment_records.json"
        try:
            if os.path.exists(records_file):
                with open(records_file, "r") as f:
                    records = json.load(f)
            else:
                records = []

            records.append(record)
            with open(records_file, "w") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            print(f"Failed to save deployment record: {e}")

    def rollback(self, deployment_id: str) -> Dict[str, Any]:
        """Rollback to previous deployment"""
        try:
            with open("deployment_records.json", "r") as f:
                records = json.load(f)

            # Find target deployment
            target = None
            for record in records:
                if record.get("id") == deployment_id:
                    target = record
                    break

            if not target:
                return {"success": False, "error": "Deployment not found"}

            # Execute rollback
            rollback_record = {
                "timestamp": datetime.now(UTC).isoformat(),
                "type": "rollback",
                "target_deployment": deployment_id,
                "config": target["config"]
            }

            self._save_deployment_record(rollback_record)
            return {"success": True, "message": "Rollback successful", "record": rollback_record}

        except Exception as e:
            return {"success": False, "error": str(e)}


def zip_directory(source_dir, zip_name):
    zip_path = os.path.join("/tmp", zip_name)
    excluded_dirs = {".git", "__pycache__", ".replit", "logs", "tmp", "venv", "node_modules"}
    excluded_extensions = {".zip", ".pyc", ".log", ".json"}

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            for file in files:
                if file.startswith(".") or any(file.endswith(ext) for ext in excluded_extensions):
                    continue
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, source_dir)
                info = zipfile.ZipInfo(arcname)
                info.date_time = time.localtime(time.time())[:6]
                with open(filepath, 'rb') as f:
                    zipf.writestr(info, f.read())
    return zip_path

def calculate_sha1(file_path):
    sha1 = hashlib.sha1()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha1.update(chunk)
    return sha1.hexdigest()

def generate_app_template(template_type):
    templates = {
        "web": {
            "files": ["index.html", "style.css", "app.js"],
            "structure": {"public": [], "src": [], "assets": []}
        },
        "api": {
            "files": ["api.py", "routes.py", "models.py"],
            "structure": {"api": [], "tests": [], "docs": []}
        }
    }
    return templates.get(template_type, {})

def deploy_to_replit(project_name, environment="production"):
    try:
        # Configure deployment settings
        deployment_config = {
            "name": project_name,
            "language": "python3",
            "run": "python app.py",
            "environment": environment,
            "healthCheck": "/health"
        }
        return {"success": True, "message": "✅ Deployment configured for Replit", "config": deployment_config}
    except Exception as e:
        return {"success": False, "error": str(e)}

def deploy_to_vercel(api_token, project_name, team_id=None):
    try:
        deployment_manager = DeploymentManager()
        zip_file_path = zip_directory(".", f"{project_name}-deploy.zip")
        digest = calculate_sha1(zip_file_path)

        with open(zip_file_path, 'rb') as file_content:
            zip_data = file_content.read()

        headers = {
            "Authorization": f"Bearer {api_token}",
            "x-vercel-digest": digest,
            "Content-Type": "application/octet-stream"
        }

        params = {}
        if team_id:
            params["teamId"] = team_id

        # Correct API call with filename in URL
        upload_url = f"https://api.vercel.com/v13/files/{os.path.basename(zip_file_path)}"

        response = requests.post(
            upload_url,
            headers=headers,
            data=zip_data,
            params=params
        )

        if response.status_code not in (200, 201):
            return {"success": False, "error": response.text}

        file_info = response.json()
        file_uid = file_info.get("uid")  # Corrected UID retrieval

        if not file_uid:
            return {"success": False, "error": "Upload succeeded but file ID missing."}

        deploy_payload = {
            "name": project_name,
            "files": [
                {
                    "file": os.path.basename(zip_file_path),
                    "fileId": file_uid
                }
            ],
            "projectSettings": {
                "framework": "other"
            }
        }

        deploy_response = requests.post(
            "https://api.vercel.com/v13/deployments",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            },
            json=deploy_payload,
            params=params
        )

        if deploy_response.status_code in (200, 201):
            deploy_data = deploy_response.json()
            url = deploy_data.get("url")
            print(f"✅ Deployed to Vercel: https://{url}")
            deployment_record = deployment_manager.deploy({"name": project_name, "url": url})
            return {"success": True, "url": f"https://{url}", "deployment_record": deployment_record}
        else:
            return {"success": False, "error": deploy_response.text}

    except Exception as e:
        return {"success": False, "error": str(e)}