import os
import io
import json
from datetime import datetime
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

    # Find or create subfolder (e.g., "2025-04-07")
    folder_id = find_or_create_subfolder(service, subfolder_name)

    # Prepare metadata and upload
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

# ✅ NEW: List recent logs (by modifiedTime, descending)
def list_recent_drive_logs(limit=5):
    service = get_drive_service()
    query = (
        f"'{ROOT_FOLDER_ID}' in parents and "
        f"mimeType = 'application/json' and trashed = false"
    )
    results = service.files().list(
        q=query,
        orderBy='modifiedTime desc',
        pageSize=limit,
        fields="files(id, name, modifiedTime)"
    ).execute()

    return [file['id'] for file in results.get('files', [])]

# ✅ NEW: Download contents of a Drive log as JSON
def download_drive_log_file(file_id):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()

    fh.seek(0)
    return json.load(fh)
