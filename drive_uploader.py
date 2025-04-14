# drive_uploader.py
import os
import io
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SERVICE_ACCOUNT_FILE = 'agentdriveuploader.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
ROOT_FOLDER_ID = '1hDKqx9xPpDXBLEWu9i6358hj8jqv9VCq'  # Your AgentLogs folder ID

def get_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=credentials)

def upload_log_to_drive(log_file_path, subfolder_name):
    service = get_drive_service()

    # Step 1: Ensure subfolder exists
    folder_id = find_or_create_subfolder(service, subfolder_name)

    # Step 2: Upload the log file
    file_metadata = {
        'name': os.path.basename(log_file_path),
        'mimeType': 'application/json',
        'parents': [folder_id]
    }
    media = MediaFileUpload(log_file_path, mimetype='application/json')
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    file_id = uploaded_file.get('id')
    shareable_link = f"https://drive.google.com/file/d/{file_id}/view"
    return file_id, shareable_link

def find_or_create_subfolder(service, subfolder_name):
    query = (
        f"'{ROOT_FOLDER_ID}' in parents and "
        f"name = '{subfolder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
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

def list_recent_drive_logs(limit=5):
    service = get_drive_service()

    # Step 1: Gather subfolders in ROOT_FOLDER_ID
    folder_query = (
        f"'{ROOT_FOLDER_ID}' in parents and "
        f"mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    folder_results = service.files().list(q=folder_query, fields="files(id, name)").execute()
    folders = folder_results.get('files', [])

    all_logs = []

    # Step 2: Collect JSON logs from each subfolder
    for folder in folders:
        folder_id = folder['id']
        log_query = (
            f"'{folder_id}' in parents and "
            f"mimeType = 'application/json' and trashed = false"
        )
        log_results = service.files().list(
            q=log_query,
            orderBy='modifiedTime desc',
            fields="files(id, name, modifiedTime)"
        ).execute()
        all_logs.extend(log_results.get('files', []))

    # Step 3: Sort and limit results
    sorted_logs = sorted(all_logs, key=lambda x: x['modifiedTime'], reverse=True)
    return [file['id'] for file in sorted_logs[:limit]]

def download_drive_log_file(file_id, timeout=30, max_retries=3):
    service = get_drive_service()
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

    fh.seek(0)
    try:
        return json.load(fh)
    except Exception as e:
        print(f"⚠️ Failed to parse Drive log: {str(e)}")
        return None

# ✅ Step 3 Fix: Alias for compatibility with /logs_from_drive
list_recent_logs = list_recent_drive_logs

# ✅ NEW FUNCTION: Search all drive logs for one matching the task ID
def download_log_by_task_id(task_id):
    """
    Searches all available Drive logs (by file name and content) for a matching taskId.
    Returns the parsed JSON log if found, or None.
    
    Args:
        task_id: Can be either a full timestamp or a processed ID
    """
    # Normalize the task_id for consistent matching
    task_id = task_id.replace(":", "_").replace(".", "_").replace("/", "_").replace("+", "_")
    task_id = task_id.split(".")[0]  # Remove microseconds if present
    service = get_drive_service()

    # 1. Gather all folders under ROOT
    folder_query = (
        f"'{ROOT_FOLDER_ID}' in parents and "
        f"mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    folders = service.files().list(q=folder_query, fields="files(id, name)").execute().get("files", [])

    # 2. Search all logs within all folders
    for folder in folders:
        log_query = (
            f"'{folder['id']}' in parents and "
            f"mimeType = 'application/json' and trashed = false"
        )
        logs = service.files().list(q=log_query, fields="files(id, name)").execute().get("files", [])

        for log_file in logs:
            if task_id in log_file['name']:
                return download_drive_log_file(log_file['id'])

            try:
                content = download_drive_log_file(log_file['id'])
                if task_id in json.dumps(content):
                    return content
            except Exception:
                continue

    return None