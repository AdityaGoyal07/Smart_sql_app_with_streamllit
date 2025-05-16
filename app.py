import streamlit as st
import base64

# 🔧 MUST BE FIRST Streamlit command
st.set_page_config(
    page_title="QueryVista - SQL Tool",
    page_icon="📊",
    layout="wide",
)

from utils import initialize_session_state, get_db_connection
from auth import is_authenticated, init_auth, logout, restore_session_from_cookies
from notifications import init_notifications, add_notification, get_unread_notification_count
from streamlit_cookies_manager import EncryptedCookieManager
import pandas as pd

# --- 🖼️ Add fixed top-right logo ---
def get_base64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_base64 = get_base64_image("static/generated-icon.png")  # Replace with your actual logo path
#gif_base64 = get_base64_image("static/a9176696b8740c402d84b55374ea0107_w200.gif")
st.markdown(
    f"""
    <style>
    .logo-container {{
        position: absolute;
        top: 25px;
        right: 25px;
        z-index: 9999;
    }}
    .logo-container img {{
        height: 100px;
    }}
    </style>
    <div class="logo-container">
        <img src="data:image/png;base64,{logo_base64}" alt="Logo">
    </div>
    """,
    unsafe_allow_html=True
)


# Initialize cookies
cookie_password = st.secrets["cookies"]["pwd"]
cookies = EncryptedCookieManager(prefix="supabase/",password=cookie_password)
if not cookies.ready():
    st.stop()

# Initialize session state
initialize_session_state()

# Initialize notifications
init_notifications()

# Initialize database schema (hidden from user)
try:
    from schema_init import initialize_database_schema
    initialize_database_schema()
except Exception as e:
    print(f"Database initialization error: {e}")

# Check for stored session in cookies for session persistence
if not is_authenticated():
    restore_session_from_cookies(cookies)

# Main function to render the home page
def main_page():
    # Header with stats and notification indicators
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

    with col1:
        st.title("QueryVista")
        st.write("Your SQL Query Assistant with AI capabilities")

    # Show user stats when authenticated
    if is_authenticated():
        with col2:
            st.metric("Files Uploaded", st.session_state.files_uploaded)
        with col3:
            st.metric("Queries Run", st.session_state.queries_run)
        with col4:
            st.metric("AI Queries", st.session_state.ai_queries)

    # Authentication status and login/logout
    auth_col1, auth_col2 = st.columns([3, 1])
    with auth_col1:
        if is_authenticated():
            st.success(f"Logged in as: {st.session_state.user_email}")
        else:
            st.warning("You are not logged in. Some features will be limited.")

    with auth_col2:
        if is_authenticated():
            if st.button("Logout", use_container_width=True):
                logout(cookies)
                st.rerun()
        else:
            if st.button("Login / Sign Up", use_container_width=True):
                st.switch_page("pages/06_Login.py")

    # Main content sections
    st.markdown("---")

    # Introduction
    st.header("Welcome to QueryVista")
    st.write("""
    QueryVista is a powerful SQL query tool that helps you analyze your data with ease.
    With built-in AI assistance, you can create and run SQL queries, manage your data files,
    and track your query history - all in one place.
    """)

    # Feature overview with three columns
    st.subheader("Key Features")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.image("static/1_rjZRlTUuIVpYMiExc5_KJg.gif")
        st.markdown("### Query Builder")
        st.write("Build SQL queries visually without writing code. Select tables, columns, and conditions through an intuitive interface.")
        if st.button("Go to Query Builder", key="go_qb", use_container_width=True):
            st.switch_page("pages/01_Query_Builder.py")

    with col2:
        st.image("static/MicrosoftSQL_ArticleCoverImage_1920x600px.gif")
        st.markdown("### Custom Query")
        st.write("Write and execute your own SQL queries directly. Ideal for experienced users who need precise control over their database operations.")
        if st.button("Go to Custom Query", key="go_cq", use_container_width=True):
            st.switch_page("pages/02_Custom_Query.py")

    with col3:
        st.image("static/1675537898711.gif",)
        st.markdown("### AI Query Assistant")
        st.write("Convert natural language to SQL. Just describe what you want in plain English, and let AI generate the SQL query for you.")
        if st.button("Go to AI Query", key="go_ai", use_container_width=True):
            st.switch_page("pages/03_AI_Query.py")

    # File management section
    st.markdown("---")
    st.subheader("File Management")
    st.write("Upload, view, and manage your data files for SQL operations.")

    if st.button("Go to File Manager", key="go_fm", use_container_width=True):
        st.switch_page("pages/04_File_Manager.py")

    # User stats and history
    st.markdown("---")
    st.subheader("Your Activity")
    st.write("View your query history and track your usage.")

    if st.button("View History", key="go_hist", use_container_width=True):
        st.switch_page("pages/05_History.py")

    # Footer
    st.markdown("---")
    st.markdown("### About QueryVista")
    st.write("""
    QueryVista is a data analysis tool that simplifies SQL operations through visual interfaces and AI assistance.
    It provides secure authentication, file management, and comprehensive history tracking to enhance your data workflows.
    """)

# Run the main page function
if __name__ == "__main__":
    main_page()
