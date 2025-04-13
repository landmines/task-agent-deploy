# deployment_manager.py
import os
import zipfile
import time
import requests
import hashlib

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
            return {"success": True, "url": f"https://{url}"}
        else:
            return {"success": False, "error": deploy_response.text}

    except Exception as e:
        return {"success": False, "error": str(e)}
