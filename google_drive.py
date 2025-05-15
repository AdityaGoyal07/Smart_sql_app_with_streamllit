import streamlit as st
import uuid
import pandas as pd
import tempfile
import os
import io
import json
from datetime import datetime, timedelta
from file_manager import upload_file, init_supabase_storage, FOLDER_GOOGLE_DRIVE
from notifications import add_notification
from sqlalchemy import text
from utils import get_db_connection
from auth import get_user_id

# Google API imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Define the scopes for accessing Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_google_credentials(user_id):
    """Get or create Google API credentials for the user"""
    # Try to load saved credentials from database
    engine = get_db_connection()
    with engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT token_data FROM google_oauth_tokens 
            WHERE user_id = :user_id
            """), {"user_id": user_id}
        )
        token_row = result.fetchone()
    
    creds = None
    if token_row:
        # Load credentials from saved token data
        token_data = json.loads(token_row[0])
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    
    # Check if credentials are valid
    if creds and creds.valid:
        return creds
    
    # If credentials expired but refreshable, refresh them
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Save refreshed credentials
            save_credentials(user_id, creds)
            return creds
        except Exception as e:
            st.error(f"Error refreshing credentials: {e}")
            return None
    
    # No valid credentials found
    return None

def save_credentials(user_id, credentials):
    """Save Google API credentials to database"""
    token_data = credentials.to_json()
    
    engine = get_db_connection()
    with engine.connect() as conn:
        # Check if the user already has saved tokens
        result = conn.execute(
            text("""
            SELECT id FROM google_oauth_tokens 
            WHERE user_id = :user_id
            """), {"user_id": user_id}
        )
        existing = result.fetchone()
        
        if existing:
            # Update existing token
            conn.execute(
                text("""
                UPDATE google_oauth_tokens 
                SET token_data = :token_data, updated_at = NOW()
                WHERE user_id = :user_id
                """), {
                    "user_id": user_id,
                    "token_data": token_data
                }
            )
        else:
            # Insert new token
            conn.execute(
                text("""
                INSERT INTO google_oauth_tokens 
                (id, user_id, token_data, created_at, updated_at)
                VALUES (:id, :user_id, :token_data, NOW(), NOW())
                """), {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "token_data": token_data
                }
            )
        
        conn.commit()
    
    return True

def list_google_drive_files(creds, mime_types=None):
    """List files from Google Drive with optional MIME type filtering"""
    try:
        service = build('drive', 'v3', credentials=creds)
        
        # Default query for spreadsheets and CSV files
        if mime_types is None:
            mime_types = [
                'application/vnd.google-apps.spreadsheet',
                'text/csv',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ]
        
        # Build query for specified MIME types
        query = " or ".join([f"mimeType='{mime}'" for mime in mime_types])
        
        # List files
        results = service.files().list(
            q=query,
            pageSize=50,
            fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime)"
        ).execute()
        
        return results.get('files', [])
    except Exception as e:
        st.error(f"Error listing Google Drive files: {e}")
        return []

def download_google_drive_file(creds, file_id, mime_type=None):
    """Download a file from Google Drive"""
    try:
        service = build('drive', 'v3', credentials=creds)
        
        # For Google Sheets, export as CSV
        if mime_type == 'application/vnd.google-apps.spreadsheet':
            response = service.files().export(
                fileId=file_id,
                mimeType='text/csv'
            ).execute()
            
            return io.BytesIO(response)
        else:
            # For regular files, download directly
            request = service.files().get_media(fileId=file_id)
            file_data = io.BytesIO()
            downloader = MediaIoBaseDownload(file_data, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_data.seek(0)
            return file_data
    except Exception as e:
        st.error(f"Error downloading file: {e}")
        return None

def upload_google_drive_file(file_info, user_id):
    """Store Google Drive file information in the database"""
    try:
        # Store in both legacy and new tables
        engine = get_db_connection()
        with engine.connect() as conn:
            # Legacy table
            conn.execute(text("""
                INSERT INTO google_drive_uploads 
                (id, user_id, drive_file_id, file_name, uploaded_at)
                VALUES (:id, :user_id, :drive_file_id, :file_name, NOW())
            """), {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "drive_file_id": file_info['id'],
                "file_name": file_info['name']
            })
            
            # Also insert into the new unified uploaded_files table
            file_path = f"Google_uploads/{user_id}/{file_info['name']}"
            conn.execute(text("""
                INSERT INTO uploaded_files
                (id, user_id, file_name, full_path, upload_type, uploaded_at)
                VALUES (:id, :user_id, :file_name, :full_path, :upload_type, NOW())
            """), {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "file_name": file_info['name'],
                "full_path": file_path,
                "upload_type": "Google_uploads"
            })
            
            conn.commit()
        
        return True, "File information stored successfully"
    except Exception as e:
        return False, f"Error storing file information: {e}"
        
def render_google_drive_ui():
    """Render UI for Google Drive integration"""
    st.header("Google Drive Integration")
    st.write("Upload files from Google Drive to Supabase")
    
    # Get user ID
    user_id = get_user_id()
    
    if not user_id:
        st.error("You must be logged in to use Google Drive integration.")
        return
    
    # Tab-based interface
    tabs = st.tabs(["Connect to Google Drive", "Browse Google Drive", "Scheduled Imports", "Upload Simulation"])
    
    with tabs[0]:
        st.subheader("Connect to Google Drive")
        
        # Check for existing credentials
        credentials = get_google_credentials(user_id)
        
        if credentials and credentials.valid:
            st.success("✅ Connected to Google Drive")
            
            # Show disconnect option
            if st.button("Disconnect from Google Drive"):
                # Remove credentials from database
                engine = get_db_connection()
                with engine.connect() as conn:
                    conn.execute(
                        text("DELETE FROM google_oauth_tokens WHERE user_id = :user_id"),
                        {"user_id": user_id}
                    )
                    conn.commit()
                
                st.success("Disconnected from Google Drive")
                st.rerun()
        else:
            st.warning("Not connected to Google Drive")
            
            st.info("""
            To connect with Google Drive, you'll need to:
            1. Create a Google Cloud project
            2. Enable the Google Drive API
            3. Create OAuth credentials
            4. Download the client secrets JSON file
            
            For this QueryVista demo, we'll use a simulated connection method.
            """)
            
            # Provide fake credentials input (this would be a real functionality in a production app)
            client_id = st.text_input("Google Client ID", key="client_id", 
                                    placeholder="your-client-id.apps.googleusercontent.com")
            client_secret = st.text_input("Google Client Secret", key="client_secret", type="password")
            
            if st.button("Connect to Google Drive (Simulation)"):
                if client_id and client_secret:
                    # Create simulated credentials
                    simulated_token = {
                        "token": str(uuid.uuid4()),
                        "refresh_token": str(uuid.uuid4()),
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "scopes": SCOPES,
                        "expiry": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
                    }
                    
                    # Store in database
                    engine = get_db_connection()
                    with engine.connect() as conn:
                        conn.execute(
                            text("""
                            INSERT INTO google_oauth_tokens 
                            (id, user_id, token_data, created_at, updated_at)
                            VALUES (:id, :user_id, :token_data, NOW(), NOW())
                            ON CONFLICT (user_id) DO UPDATE 
                            SET token_data = :token_data, updated_at = NOW()
                            """), {
                                "id": str(uuid.uuid4()),
                                "user_id": user_id,
                                "token_data": json.dumps(simulated_token)
                            }
                        )
                        conn.commit()
                    
                    st.success("Connected to Google Drive (Simulated)")
                    st.rerun()
                else:
                    st.error("Please enter both Client ID and Client Secret")
    
    with tabs[1]:
        st.subheader("Browse Google Drive Files")
        
        credentials = get_google_credentials(user_id)
        
        if not credentials:
            st.warning("Please connect to Google Drive first")
        else:
            st.success("Connected to Google Drive")
            
            # File type filter
            file_types = st.multiselect(
                "File Types", 
                ["CSV Files", "Excel Files", "Google Sheets"],
                default=["CSV Files", "Excel Files", "Google Sheets"]
            )
            
            # Map selected types to MIME types
            mime_types = []
            if "CSV Files" in file_types:
                mime_types.append("text/csv")
            if "Excel Files" in file_types:
                mime_types.extend(["application/vnd.ms-excel", 
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"])
            if "Google Sheets" in file_types:
                mime_types.append("application/vnd.google-apps.spreadsheet")
            
            # Show refresh button
            if st.button("Refresh File List"):
                st.session_state.drive_files = "refresh_triggered"
            
            # Simulated file list
            if "drive_files" not in st.session_state or st.session_state.drive_files == "refresh_triggered":
                # Generate some example files
                st.session_state.drive_files = [
                    {
                        "id": "file1",
                        "name": "Sample CSV Data.csv",
                        "mimeType": "text/csv",
                        "modifiedTime": "2023-05-15T14:30:00Z"
                    },
                    {
                        "id": "file2",
                        "name": "Financial Report.xlsx",
                        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "modifiedTime": "2023-06-22T09:15:00Z"
                    },
                    {
                        "id": "file3",
                        "name": "Customer Data.gsheet",
                        "mimeType": "application/vnd.google-apps.spreadsheet",
                        "modifiedTime": "2023-07-01T11:45:00Z"
                    }
                ]
            
            # Display file list
            st.write(f"Found {len(st.session_state.drive_files)} files")
            
            for file in st.session_state.drive_files:
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"📄 {file['name']}")
                
                with col2:
                    mime_display = file['mimeType'].split('/')[-1]
                    st.write(f"Type: {mime_display}")
                
                with col3:
                    if st.button("Import", key=f"import_{file['id']}"):
                        st.info(f"Importing {file['name']}...")
                        
                        # In a real app, we would download the file here
                        # Simulate download with a simple dummy file
                        if "csv" in file['mimeType']:
                            content = "name,age\nJohn,30\nJane,25"
                        else:
                            content = "dummy,data\n1,2\n3,4"
                        
                        # Create file-like object
                        file_obj = io.BytesIO(content.encode('utf-8'))
                        file_obj.name = file['name']
                        
                        # Upload to Supabase
                        supabase = init_supabase_storage()
                        success, message = upload_file(
                            file_obj,
                            file['name'],
                            source="google_drive",
                            supabase=supabase
                        )
                        
                        if success:
                            # Store metadata
                            upload_google_drive_file(file, user_id)
                            
                            # Add notification
                            add_notification("File Imported", f"{file['name']} imported from Google Drive")
                            
                            st.success(f"Successfully imported {file['name']}")
                        else:
                            st.error(f"Failed to import file: {message}")
                
                st.divider()
    
    with tabs[2]:
        st.subheader("Scheduled Imports")
        
        if not get_google_credentials(user_id):
            st.warning("Please connect to Google Drive first")
        else:
            # Scheduled imports UI
            st.info("Set up automatic imports from Google Drive")
            
            # File selector
            selected_file = st.selectbox(
                "Select file to schedule",
                [file["name"] for file in st.session_state.get("drive_files", [])]
            )
            
            # Schedule options
            schedule_frequency = st.selectbox(
                "Import frequency",
                ["Daily", "Weekly", "Monthly"]
            )
            
            time_options = [f"{h:02d}:00" for h in range(24)]
            schedule_time = st.selectbox("Time of day (UTC)", time_options)
            
            # Initialize schedule_day as None by default
            schedule_day = None
            
            if schedule_frequency == "Weekly":
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                schedule_day = st.selectbox("Day of week", days)
            elif schedule_frequency == "Monthly":
                days = list(range(1, 29))
                schedule_day = st.selectbox("Day of month", days)
            
            if st.button("Save Schedule"):
                if selected_file:
                    # Get file info
                    file_info = next((f for f in st.session_state.get("drive_files", []) if f["name"] == selected_file), None)
                    
                    if file_info:
                        # Save schedule to database
                        engine = get_db_connection()
                        with engine.connect() as conn:
                            conn.execute(
                                text("""
                                INSERT INTO scheduled_imports
                                (id, user_id, drive_file_id, file_name, frequency, schedule_time, schedule_day, created_at)
                                VALUES (:id, :user_id, :drive_file_id, :file_name, :frequency, :schedule_time, :schedule_day, NOW())
                                """), {
                                    "id": str(uuid.uuid4()),
                                    "user_id": user_id,
                                    "drive_file_id": file_info["id"],
                                    "file_name": file_info["name"],
                                    "frequency": schedule_frequency,
                                    "schedule_time": schedule_time,
                                    "schedule_day": str(schedule_day) if schedule_day is not None else None
                                }
                            )
                            conn.commit()
                        
                        st.success(f"Scheduled {selected_file} for {schedule_frequency.lower()} import")
                        add_notification("Schedule Created", f"{selected_file} scheduled for {schedule_frequency.lower()} import")
                    else:
                        st.error("File information not found")
                else:
                    st.error("Please select a file to schedule")
            
            # Show existing schedules
            st.subheader("Existing Schedules")
            
            # In a real app, fetch from database
            engine = get_db_connection()
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                    SELECT id, file_name, frequency, schedule_time, schedule_day, created_at
                    FROM scheduled_imports
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    """), {"user_id": user_id}
                )
                
                schedules = []
                for row in result:
                    schedules.append({
                        "id": row[0],
                        "file_name": row[1],
                        "frequency": row[2],
                        "schedule_time": row[3],
                        "schedule_day": row[4],
                        "created_at": row[5]
                    })
            
            if schedules:
                for schedule in schedules:
                    col1, col2, col3 = st.columns([3, 2, 1])
                    
                    with col1:
                        st.write(f"📄 {schedule['file_name']}")
                    
                    with col2:
                        schedule_desc = f"{schedule['frequency']}"
                        if schedule['schedule_day']:
                            schedule_desc += f" on {schedule['schedule_day']}"
                        schedule_desc += f" at {schedule['schedule_time']}"
                        st.write(schedule_desc)
                    
                    with col3:
                        if st.button("Delete", key=f"delete_{schedule['id']}"):
                            engine = get_db_connection()
                            with engine.connect() as conn:
                                conn.execute(
                                    text("DELETE FROM scheduled_imports WHERE id = :id"),
                                    {"id": schedule['id']}
                                )
                                conn.commit()
                            
                            st.success("Schedule deleted")
                            st.rerun()
                    
                    st.divider()
            else:
                st.info("No scheduled imports yet")
    
    with tabs[3]:
        st.subheader("Upload Simulation")
        st.info("Upload a file and we'll simulate it coming from Google Drive")
        
        # File uploader for simulation
        uploaded_file = st.file_uploader(
            "Upload a file to simulate Google Drive import", 
            type=["csv", "xlsx", "xls"],
            key="google_drive_simulation"
        )
        
        if uploaded_file is not None:
            st.success(f"File selected: {uploaded_file.name}")
            
            if st.button("Import from Google Drive"):
                # Create a simulated Google Drive file info
                file_info = {
                    'id': str(uuid.uuid4()),
                    'name': uploaded_file.name,
                    'mimeType': uploaded_file.type
                }
                
                # Upload to Supabase with Google_uploads prefix
                supabase = init_supabase_storage()
                success, message = upload_file(
                    uploaded_file, 
                    uploaded_file.name,  # Just pass the filename
                    source="google_drive",  # Specify the source as google_drive
                    supabase=supabase
                )
                
                if success:
                    # Store Google Drive metadata
                    upload_google_drive_file(file_info, user_id)
                    
                    # Update counters and notifications
                    st.session_state.files_uploaded = st.session_state.get("files_uploaded", 0) + 1
                    add_notification("File Imported", f"{uploaded_file.name} imported from Google Drive")
                    
                    st.success(f"Successfully imported {uploaded_file.name} from Google Drive")
                else:
                    st.error(f"Failed to import file: {message}")
                    
                    with st.expander("Error Details"):
                        st.code(message)
                        st.markdown("""
                        ### Common issues:
                        1. Row Level Security (RLS) policies not properly configured
                        2. Missing tables in the database
                        3. Insufficient permissions
                        """)
                        
                        # Display RLS policy suggestion
                        st.info("""
                        Make sure you have the following RLS policy in Supabase:
                        
                        ```sql
                        -- For uploads
                        CREATE POLICY "Users can upload their own files"
                        ON storage.objects
                        FOR INSERT WITH CHECK (
                          name LIKE 'from_pc/' || auth.uid() || '/%' OR
                          name LIKE 'Google_uploads/' || auth.uid() || '/%' OR
                          name LIKE 'scheduled_uploads/' || auth.uid() || '/%'
                        );
                        ```
                        """)
