import streamlit as st
import pandas as pd
from supabase import create_client, Client
from sqlalchemy import text
from io import BytesIO
import uuid
import os, time

from auth import get_user_id, is_authenticated
from notifications import add_notification
from utils import get_db_connection
from file_sanitizer import sanitize_filename, sanitize_column_names

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", st.secrets.get("supabase_auth", {}).get("URL"))
SUPABASE_KEY = os.getenv("SUPABASE_KEY", st.secrets.get("supabase_auth", {}).get("KEY"))
BUCKET_NAME = "sql-bucket"
UPLOAD_TYPES = ['pc', 'google_drive', 'scheduled']

@st.cache_resource
def init_supabase_storage(access_token=None, refresh_token=None) -> Client:
    """Initialize Supabase client with optional session tokens"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing Supabase credentials")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    if access_token and refresh_token:
        client.auth.set_session(access_token, refresh_token)
    return client

def _get_authenticated_supabase():
    """Get Supabase client with authenticated user session"""
    if not is_authenticated():
        return None
    return init_supabase_storage(
        access_token=st.session_state.get("access_token"),
        refresh_token=st.session_state.get("refresh_token")
    )

def upload_file(file, upload_type='pc', supabase=None):
    """Upload file to user-specific Supabase storage and DB with progress feedback"""
    user_id = get_user_id()
    if not user_id:
        st.error("Please log in to upload files.")
        return False, "User not authenticated"

    if upload_type not in UPLOAD_TYPES:
        return False, f"Invalid upload type: {upload_type}"

    progress = st.progress(0, text="Starting upload...")

    try:
        progress.progress(10, text="Authenticating user...")
        supabase = supabase or _get_authenticated_supabase()

        progress.progress(25, text="Preparing file...")
        sanitized_name = sanitize_filename(file.name)
        file_path = f"{user_id}/{upload_type}/{sanitized_name}"
        file_bytes = file.getvalue()

        progress.progress(35, text="Checking for existing file...")
        existing_files = supabase.storage.from_(BUCKET_NAME).list(f"{user_id}/{upload_type}")
        if any(f["name"] == file.name for f in existing_files):
            progress.empty()
            return False, "File already exists. Please rename or delete it before uploading."

        progress.progress(50, text="Uploading to storage...")
        supabase.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": _get_content_type(file.name)}
        )

        progress.progress(75, text="Saving metadata to database...")
        engine = get_db_connection()
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO uploaded_files 
                (id, user_id, file_name, full_path, upload_type, uploaded_at)
                VALUES (:id, :user_id, :name, :path, :type, NOW())
            """), {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "name": file.name,
                "path": file_path,
                "type": upload_type
            })
            conn.commit()

        progress.progress(100, text="Upload complete!")
        time.sleep(0.5)  # small delay to show completion
        progress.empty()

        add_notification("File Uploaded", f"{file.name} uploaded successfully")
        return True, file_path

    except Exception as e:
        progress.empty()
        error = str(e)
        if "Unauthorized" in error:
            _show_rls_guidance(user_id)
        return False, f"Upload failed: {error}"

def list_files(supabase=None, upload_type=None):
    """List user's uploaded files, optionally filtered by type"""
    user_id = get_user_id()
    if not user_id:
        return []

    try:
        supabase = supabase or _get_authenticated_supabase()

        # Attempt to fetch from DB
        engine = get_db_connection()
        with engine.connect() as conn:
            query = text("""
                SELECT file_name, full_path, upload_type, uploaded_at
                FROM uploaded_files
                WHERE user_id = :user_id
                """ + ("AND upload_type = :type" if upload_type else "")
            )
            params = {"user_id": user_id}
            if upload_type:
                params["type"] = upload_type
            result = conn.execute(query, params)
            files = [dict(row) for row in result.mappings()]

        # Fallback to storage listing
        if not files:
            storage_path = f"{user_id}/{upload_type or ''}"
            storage_files = supabase.storage.from_(BUCKET_NAME).list(storage_path)
            files = [{
                'file_name': f['name'],
                'full_path': f'{storage_path}/{f["name"]}',
                'upload_type': upload_type or 'unknown',
                'uploaded_at': None,
                'verified': False
            } for f in storage_files if not f['name'].endswith('/')]

        return files

    except Exception as e:
        st.error(f"Error listing files: {str(e)}")
        return []

def delete_file(file_path, supabase=None):
    """Delete file from Supabase and metadata DB"""
    user_id = get_user_id()
    if not user_id or f"{user_id}/" not in file_path:
        return False, "Unauthorized deletion"

    try:
        supabase = supabase or _get_authenticated_supabase()

        supabase.storage.from_(BUCKET_NAME).remove([file_path])

        engine = get_db_connection()
        with engine.connect() as conn:
            conn.execute(text("""
                DELETE FROM uploaded_files
                WHERE user_id = :user_id AND full_path = :path
            """), {"user_id": user_id, "path": file_path})
            conn.commit()

        return True, "File deleted"

    except Exception as e:
        return False, str(e)

def download_file(file_path, supabase=None):
    """Download file content from Supabase"""
    try:
        supabase = supabase or _get_authenticated_supabase()
        return supabase.storage.from_(BUCKET_NAME).download(file_path)
    except Exception as e:
        st.error(f"Download failed: {str(e)}")
        return None

def parse_file_to_dataframe(file_bytes, filename=None):
    try:
        if filename and filename.endswith('.csv'):
            df = pd.read_csv(BytesIO(file_bytes))
        elif filename and filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(BytesIO(file_bytes))
        else:
            return None, "Unsupported file type"

        df = sanitize_column_names(df)  # ✅ Sanitize column names after reading
        return df, None

    except Exception as e:
        return None, str(e)

def _get_content_type(filename):
    """Get MIME type from extension"""
    ext = filename.split('.')[-1].lower()
    return {
        'csv': 'text/csv',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }.get(ext, 'application/octet-stream')

def _show_rls_guidance(user_id):
    """Display RLS policy help in UI"""
    with st.expander("RLS Policy Setup Help"):
        st.markdown(f"""
        Required Supabase storage policy for user **{user_id}**:
        ```sql
        CREATE POLICY "User file access" ON storage.objects
        FOR ALL USING (
            bucket_id = 'sql-bucket'
            AND name LIKE '{user_id}/%'
        );
        ```
        """)
def get_signed_url(file_path, supabase=None, expires_in=300):
    supabase = supabase or _get_authenticated_supabase()
    url_response = supabase.storage.from_(BUCKET_NAME).create_signed_url(file_path, expires_in)
    if url_response.get('signedURL'):
        return url_response['signedURL']
    else:
        return None
