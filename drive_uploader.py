import os
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SERVICE_ACCOUNT_FILE = 'agentdriveuploader-debaa1714b6c.json'
SCOPES = ['https://www.googleapis.com/auth/drive.file']
ROOT_FOLDER_ID = '1hDKqx9xPpDXBLEWu9i6358hj8jqv9VCq'  # Your AgentLogs folder ID

def upload_log_to_drive(log_file_path, subfolder_name):
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=credentials)

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
    # Look for existing subfolder in your AgentLogs folder
    query = (
        f"'{ROOT_FOLDER_ID}' in parents and "
        f"name = '{subfolder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])

    if folders:
        return folders[0]['id']  # Use existing

    # Create new subfolder
    folder_metadata = {
        'name': subfolder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [ROOT_FOLDER_ID]
    }
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    return folder.get('id')
