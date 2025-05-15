import streamlit as st
import requests
from auth import is_authenticated
from file_manager import (
    init_supabase_storage,
    list_files,
    upload_file,
    delete_file,
    download_file,
    get_signed_url,
    parse_file_to_dataframe
)
# from google_drive import render_google_drive_ui
from notifications import add_notification, init_notifications
from auth_redirect import check_auth_and_redirect
from collections import defaultdict

# Set page config
st.set_page_config(
    page_title="File Manager - SQL Tool",
    page_icon="📁",
    layout="wide"
)

# Initialize notifications
init_notifications()

# Check authentication
if not check_auth_and_redirect():
    st.stop()

# Initialize Supabase storage client
supabase = init_supabase_storage()

# Page title and instructions
st.title("File Manager")
st.write("""
Upload, view, and manage your CSV and XLSX files in the Supabase storage.
These files can be used as data sources for your SQL queries.
""")

with st.expander("How to use the File Manager", expanded=False):
    st.markdown("""
### Upload Files
1. Select one or more CSV or Excel files using the file upload widget
2. Files will be automatically categorized by upload type
3. Click 'Upload to Supabase' to store them in your secure storage bucket
4. Files will become available for SQL queries once uploaded

### Manage Files
- **View**: Preview the contents of uploaded CSV and Excel files
- **Delete**: Remove files that you no longer need
- **Download**: Retrieve a copy of the stored files

### File Types
- **CSV files** (.csv): Comma-separated values
- **Excel files** (.xlsx, .xls): Microsoft Excel spreadsheets

Your files are securely stored in Supabase and only accessible to you.
""")

# Create tabs
upload_tab, files_tab, google_drive_tab = st.tabs(["Upload Files", "Manage Files", "Google Drive"])

# -------- Upload Files Tab --------
with upload_tab:
    st.header("Upload Files from PC")
    st.write("Upload CSV or XLSX files to your Supabase storage")

    upload_type = 'pc'

    uploaded_files = st.file_uploader(
        "Upload files",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True
    )

    if st.button("Upload to Supabase"):
        if uploaded_files:
            for file in uploaded_files:
                success, message = upload_file(file, upload_type=upload_type, supabase=supabase)
                if success:
                    st.success(f"{file.name} uploaded successfully!")
                else:
                    st.error(f"Error uploading {file.name}: {message}")
        else:
            st.warning("Please select at least one file.")

# -------- Manage Files Tab --------
with files_tab:
    st.header("Manage Files")
    st.write("View and manage files in your Supabase storage")

    if st.button("Refresh File List"):
        st.rerun()

    try:
        files = list_files(supabase)

        if not files:
            st.warning("No files found in storage.")
            with st.expander("Why can't I see my files?", expanded=True):
                st.markdown("""
#### Possible reasons:
1. **No files uploaded yet**
2. **Row Level Security (RLS) issues**
   - Ensure authenticated users can access their own files in Supabase
3. **Connection issues**
                """)
        else:
            st.success(f"Found {len(files)} files in storage")
    except Exception as e:
        st.error(f"Error listing files: {str(e)}")
        with st.expander("Troubleshooting Steps", expanded=True):
            st.markdown("""
### RLS Fix
```sql
CREATE POLICY "User file access" ON storage.objects
FOR ALL USING (
        bucket_id = 'sql-bucket'
        AND name LIKE auth.uid() || '/%'
);
```
            """)
        files = []

    if files:
        grouped = defaultdict(list)
        for file in files:
            grouped[file.get("upload_type", "unknown")].append(file)

        for group, group_files in grouped.items():
            with st.expander(f"{group.replace('_', ' ').title()} ({len(group_files)})", expanded=True):
                for file in group_files:
                    col1, col2, col3, col4 = st.columns([4, 1, 1, 2])
                    with col1:
                        display_name = file.get('file_name') or file.get('display_name') or file.get('name') or "Unnamed File" 
                        st.write(f"📄 **{display_name}**")
                        st.caption(f"Path: {file.get('full_path', '')}")

                    unique_key_base = file.get('name') or file.get('display_name') or file.get('full_path')

                    with col2:
                        if st.button("View", key=f"view_{unique_key_base}"):
                            signed_url = get_signed_url(file['full_path'], supabase)
                            if signed_url:
                                try:
                                    import requests
                                    response = requests.get(signed_url)
                                    if response.status_code == 200:
                                        df, error = parse_file_to_dataframe(response.content, filename=display_name)
                                        if error:
                                            st.error(f"Error reading file: {error}")
                                        else:
                                            st.session_state.viewed_file = {
                                                'name': display_name,
                                                'df': df,
                                                'path': file['full_path']
                                            }
                                            st.rerun()
                                    else:
                                        st.error(f"Failed to download file: Status {response.status_code}")
                                except Exception as e:
                                    st.error(f"Error loading file from URL: {e}")
                            else:
                                st.error("Failed to get access URL for file")



                    with col3:
                        if st.button("Delete", key=f"delete_{unique_key_base}"):
                            success, message = delete_file(file['full_path'], supabase)
                            if success:
                                st.success(f"Deleted {display_name}")
                                add_notification("File Deleted", f"{display_name} was deleted successfully.")
                                st.rerun()
                            else:
                                st.error(f"Error deleting file: {message}")

                    with col4:
                        st.download_button(
                            label="Download",
                            data=download_file(file['full_path'], supabase),
                            file_name=display_name,
                            mime="application/octet-stream",
                            key=f"download_{unique_key_base}"
                        )

                    st.divider()

    if 'viewed_file' in st.session_state:
        st.subheader(f"File Preview: {st.session_state.viewed_file['name']}")
        st.dataframe(st.session_state.viewed_file['df'])

        if st.button("Use this file for queries"):
            st.session_state.query_file = {
                'name': st.session_state.viewed_file['name'],
                'df': st.session_state.viewed_file['df'],
                'path': st.session_state.viewed_file['path']
            }
            st.success(f"Selected {st.session_state.viewed_file['name']} for queries")

        if st.button("Close Preview"):
            del st.session_state.viewed_file
            st.rerun()

# -------- Google Drive Tab --------
with google_drive_tab:
    st.header("Google Drive Integration")
    st.write("Connect your Google Drive and upload files directly.")
    # render_google_drive_ui()
    st.info("Coming soon: Scheduled uploads and Google Drive file picker")