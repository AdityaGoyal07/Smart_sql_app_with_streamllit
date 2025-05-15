import streamlit as st
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
import os
from datetime import datetime

def initialize_database_schema(engine=None):
    """Create and initialize the database schema if tables don't exist"""
    try:
        if engine is None:
            try:
                POSTGRES_HOST = st.secrets["supabase_db"]["HOST"]
                POSTGRES_PORT = st.secrets["supabase_db"]["PORT"]
                POSTGRES_USER = st.secrets["supabase_db"]["USER"]
                POSTGRES_PASSWORD = st.secrets["supabase_db"]["PWD"]
                POSTGRES_DB = st.secrets["supabase_db"]["DB"]
            except:
                POSTGRES_HOST = os.getenv("SUPABASE_HOST")
                POSTGRES_PORT = os.getenv("SUPABASE_PORT")
                POSTGRES_USER = os.getenv("SUPABASE_USER")
                POSTGRES_PASSWORD = os.getenv("SUPABASE_PASSWORD")
                POSTGRES_DB = os.getenv("SUPABASE_DB")

            connection_string = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
            engine = create_engine(connection_string, connect_args={"connect_timeout":10})

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

            if "__main__" == __name__:
                st.success("Database connection successful!")

            metadata = MetaData()

            # Users table (linked to Supabase auth.uid)
            Table(
                'metadata_users', metadata,
                Column('uid', UUID(as_uuid=True), primary_key=True),
                Column('email', String, unique=True),
                Column('full_name', String),
                Column('phone', String),
                Column('dob', DateTime),
                Column('created_at', DateTime),
                Column('updated_at', DateTime)
            )

            # File uploads from PC
            Table(
                'file_uploads_from_pc', metadata,
                Column('id', UUID(as_uuid=True), primary_key=True),
                Column('user_id', UUID(as_uuid=True), ForeignKey('metadata_users.uid')),
                Column('file_name', String),
                Column('file_path', String),
                Column('uploaded_at', DateTime),
                Column('file_size', Integer)
            )

            # Google Drive uploads
            Table(
                'google_drive_uploads', metadata,
                Column('id', UUID(as_uuid=True), primary_key=True),
                Column('user_id', UUID(as_uuid=True), ForeignKey('metadata_users.uid')),
                Column('drive_file_id', String),
                Column('file_name', String),
                Column('uploaded_at', DateTime)
            )

            # Query history
            Table(
                'query_history', metadata,
                Column('id', UUID(as_uuid=True), primary_key=True),
                Column('user_id', UUID(as_uuid=True), ForeignKey('metadata_users.uid')),
                Column('query_text', String),
                Column('query_type', String),
                Column('executed_at', DateTime),
                Column('status', String),
                Column('error_message', String)
            )

            # Unified file uploads
            Table(
                'uploaded_files', metadata,
                Column('id', UUID(as_uuid=True), primary_key=True),
                Column('user_id', UUID(as_uuid=True), ForeignKey('metadata_users.uid')),
                Column('file_name', String),
                Column('full_path', String),
                Column('upload_type', String),
                Column('uploaded_at', DateTime)
            )

            # Google OAuth tokens
            Table(
                'google_oauth_tokens', metadata,
                Column('id', UUID(as_uuid=True), primary_key=True),
                Column('user_id', UUID(as_uuid=True), ForeignKey('metadata_users.uid'), unique=True),
                Column('token_data', String),
                Column('created_at', DateTime),
                Column('updated_at', DateTime)
            )

            # Scheduled imports
            Table(
                'scheduled_imports', metadata,
                Column('id', UUID(as_uuid=True), primary_key=True),
                Column('user_id', UUID(as_uuid=True), ForeignKey('metadata_users.uid')),
                Column('drive_file_id', String),
                Column('file_name', String),
                Column('frequency', String),
                Column('schedule_time', String),
                Column('schedule_day', String),
                Column('created_at', DateTime),
                Column('last_run', DateTime)
            )
            
            # User sessions table
            Table(
                'user_sessions', metadata,
                Column('user_id', UUID(as_uuid=True), ForeignKey('metadata_users.uid'), primary_key=True),
                Column('email', String, nullable=False),
                Column('access_token', String, nullable=False),
                Column('refresh_token', String, nullable=False),
                Column('created_at', DateTime, default=datetime.utcnow),
                Column('last_active', DateTime, default=datetime.utcnow)
            )

            metadata.create_all(engine, checkfirst=True)

            if "__main__" == __name__:
                st.success("Database schema initialized successfully!")

            return engine

    except Exception as e:
        st.error(f"Database initialization error: {e}")
        raise e

if __name__ == "__main__":
    st.title("Database Schema Initialization")
    initialize_database_schema()
