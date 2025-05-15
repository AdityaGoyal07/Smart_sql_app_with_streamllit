import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine
import time
import os

# Postgres Database Connection Details
try:
    POSTGRES_HOST = st.secrets["supabase_db"]["HOST"]
    POSTGRES_PORT = st.secrets["supabase_db"]["PORT"]
    POSTGRES_USER = st.secrets["supabase_db"]["USER"]
    POSTGRES_PASSWORD = st.secrets["supabase_db"]["PWD"]
    POSTGRES_DB = st.secrets["supabase_db"]["DB"]
except:
    # Fallback for environment variables
    POSTGRES_HOST = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT")
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB = os.getenv("POSTGRES_DB")

@st.cache_resource
def get_db_connection():
    """Create and return a SQLAlchemy engine for the Postgres database"""
    connection_string = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    
    try:
        engine = create_engine(connection_string)
        # Test connection
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        
        # Initialize the database schema
        from schema_init import initialize_database_schema
        initialize_database_schema(engine)
        
        return engine
    except Exception as e:
        st.error(f"Database connection error: {e}")
        raise e

def initialize_session_state():
    """Initialize all session state variables needed across the app"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    
    if "refresh_token" not in st.session_state:
        st.session_state.refresh_token = None
    
    if "files_uploaded" not in st.session_state:
        st.session_state.files_uploaded = 0
    
    if "queries_run" not in st.session_state:
        st.session_state.queries_run = 0
    
    if "ai_queries" not in st.session_state:
        st.session_state.ai_queries = 0
