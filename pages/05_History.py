import streamlit as st
from auth import is_authenticated
from history import render_history_ui
from notifications import init_notifications
from auth_redirect import check_auth_and_redirect

# Set page config
st.set_page_config(
    page_title="History - SQL Tool",
    page_icon="📜",
    layout="wide"
)

# Initialize notifications
init_notifications()

# Check authentication using the unified function
if not check_auth_and_redirect():
    st.stop()

# Page content
st.title("Query & Action History")
st.write("""
View your query and action history. 
This page shows a log of your queries, file uploads, and other actions performed in the application.
""")

# Render history UI
render_history_ui()
