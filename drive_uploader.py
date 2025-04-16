
# drive_uploader.py
import os
import io
import json
from typing import Optional, Tuple
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive']
ROOT_FOLDER_ID = '1hDKqx9xPpDXBLEWu9i6358hj8jqv9VCq'  # Your AgentLogs folder ID

def get_drive_service():
    """Initialize and return Google Drive service with proper error handling."""
    creds_json = os.environ.get('GOOGLE_DRIVE_CREDENTIALS')
    if not creds_json:
        print("⚠️ Missing Google Drive credentials")
        return None

    try:
        info = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=SCOPES
        )
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        print(f"❌ Drive service creation failed: {str(e)}")
        return None

def find_or_create_subfolder(service, subfolder_name: str) -> Optional[str]:
    """Find or create a subfolder in the root folder."""
    if not service:
        return None
        
    try:
        query = (
            f"'{ROOT_FOLDER_ID}' in parents and "
            f"name = '{subfolder_name}' and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            "trashed = false"
        )

        results = service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])

        if folders:
            return folders[0]['id']

        folder_metadata = {
            'name': subfolder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [ROOT_FOLDER_ID]
        }

        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')

    except Exception as e:
        print(f"❌ Error in find_or_create_subfolder: {e}")
        return None

def upload_log_to_drive(log_file_path: str, subfolder_name: str) -> Tuple[Optional[str], Optional[str]]:
    """Upload a log file to Google Drive with proper error handling."""
    try:
        service = get_drive_service()
        if not service:
            print("⚠️ Drive service unavailable - saving locally only")
            return None, None

        folder_id = find_or_create_subfolder(service, subfolder_name)
        if not folder_id:
            print("❌ Failed to create or find subfolder")
            return None, None

        if not os.path.exists(log_file_path):
            print(f"❌ Log file not found: {log_file_path}")
            return None, None

        file_metadata = {
            'name': os.path.basename(log_file_path),
            'mimeType': 'application/json',
            'parents': [folder_id]
        }

        media = MediaFileUpload(log_file_path, mimetype='application/json', resumable=True)
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        file_id = file.get('id')
        if not file_id:
            print("❌ Upload succeeded but no file ID returned")
            return None, None

        shareable_link = f"https://drive.google.com/file/d/{file_id}/view"
        print(f"✅ Upload succeeded: {shareable_link}")
        return file_id, shareable_link

    except Exception as e:
        print(f"❌ Drive upload failed: {str(e)}")
        return None, None

def list_recent_drive_logs(limit: int = 5) -> list:
    """List recent logs from Drive with proper error handling."""
    service = get_drive_service()
    if not service:
        print("❌ Drive service unavailable")
        return []

    try:
        folder_query = (
            f"'{ROOT_FOLDER_ID}' in parents and "
            f"mimeType = 'application/vnd.google-apps.folder' and "
            "trashed = false"
        )
        folder_results = service.files().list(q=folder_query, fields="files(id, name)").execute()
        folders = folder_results.get('files', [])

        all_logs = []
        for folder in folders:
            log_query = (
                f"'{folder['id']}' in parents and "
                f"mimeType = 'application/json' and "
                "trashed = false"
            )
            log_results = service.files().list(
                q=log_query,
                orderBy='modifiedTime desc',
                fields="files(id, name, modifiedTime)"
            ).execute()
            all_logs.extend(log_results.get('files', []))

        sorted_logs = sorted(all_logs, key=lambda x: x['modifiedTime'], reverse=True)
        return [file['id'] for file in sorted_logs[:limit]]
    except Exception as e:
        print(f"❌ Error listing logs: {str(e)}")
        return []

def download_drive_log_file(file_id: str, timeout: int = 30, max_retries: int = 3) -> Optional[dict]:
    """Download and parse a log file from Drive with proper error handling."""
    service = get_drive_service()
    if not service:
        print("❌ Could not initialize Drive service")
        return None

    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    import socket
    socket.setdefaulttimeout(timeout)

    print(f"🔄 Attempting to download Drive file: {file_id}")

    retry_count = 0
    while retry_count < max_retries:
        try:
            done = False
            chunk_count = 0
            while not done and chunk_count < 5:  # Limit chunks
                status, done = downloader.next_chunk()
                chunk_count += 1
            if not done:
                raise TimeoutError("Download taking too long")
            fh.seek(0)
            return json.load(fh)
        except Exception as e:
            print(f"⚠️ Drive download attempt {retry_count + 1} failed: {str(e)}")
            retry_count += 1
            if retry_count >= max_retries:
                print("❌ All Drive download attempts failed")
                return None

    return None

# Alias for compatibility
list_recent_logs = list_recent_drive_logs

def download_log_by_task_id(task_id: str) -> Optional[dict]:
    """Download a log file by task ID with proper error handling."""
    task_id = task_id.replace(":", "_").replace(".", "_").replace("/", "_").replace("+", "_")
    task_id = task_id.split(".")[0]  # Remove microseconds if present
    
    service = get_drive_service()
    if not service:
        print("❌ Drive service unavailable")
        return None

    try:
        folder_query = (
            f"'{ROOT_FOLDER_ID}' in parents and "
            f"mimeType = 'application/vnd.google-apps.folder' and "
            "trashed = false"
        )
        folders = service.files().list(q=folder_query, fields="files(id, name)").execute().get("files", [])

        for folder in folders:
            log_query = (
                f"'{folder['id']}' in parents and "
                f"mimeType = 'application/json' and "
                "trashed = false"
            )
            logs = service.files().list(q=log_query, fields="files(id, name)").execute().get("files", [])

            for log_file in logs:
                if task_id in log_file['name']:
                    return download_drive_log_file(log_file['id'])

                try:
                    content = download_drive_log_file(log_file['id'])
                    if content and task_id in json.dumps(content):
                        return content
                except Exception as e:
                    print(f"Error reading log file {log_file['id']}: {str(e)}")
                    continue

        return None
    except Exception as e:
        print(f"❌ Error searching for task ID: {str(e)}")
        return None
