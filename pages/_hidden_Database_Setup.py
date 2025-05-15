import streamlit as st
from utils import get_db_connection
from sqlalchemy import text, inspect
import pandas as pd

# Set page config
st.set_page_config(
    page_title="Database Setup - SQL Tool",
    page_icon="🗄️",
    layout="wide"
)

# Main function
def main():
    st.title("Database Setup and Configuration")
    st.write("""
    This page allows you to check your database setup and initialize the schema.
    """)
    
    # Try to get database connection
    try:
        with st.spinner("Connecting to database..."):
            engine = get_db_connection()
        
        # Connection successful
        st.success("✅ Database connection successful!")
        
        # Show database connection info
        conn_info = {
            "Database host": st.secrets["supabase_db"]["HOST"],
            "Database port": st.secrets["supabase_db"]["PORT"],
            "Database name": st.secrets["supabase_db"]["DB"],
            "Database user": st.secrets["supabase_db"]["USER"]
        }
        
        st.subheader("Connection Information")
        for key, value in conn_info.items():
            st.write(f"**{key}:** {value}")
        
        # Check tables
        st.subheader("Database Tables")
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if tables:
            st.write(f"Found {len(tables)} tables in the database.")
            for table in tables:
                with st.expander(f"Table: {table}"):
                    # Get columns
                    columns = inspector.get_columns(table)
                    column_data = []
                    for col in columns:
                        column_data.append({
                            "Column Name": col["name"],
                            "Type": str(col["type"]),
                            "Nullable": "Yes" if col.get("nullable", True) else "No",
                            "Default": col.get("default", "None")
                        })
                    
                    st.dataframe(pd.DataFrame(column_data))
                    
                    # Row count
                    try:
                        with engine.connect() as conn:
                            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                            count = result.scalar()
                            st.write(f"**Row count:** {count}")
                    except:
                        st.write("**Row count:** Unable to retrieve")
        else:
            st.warning("No tables found in the database. The schema may not be initialized.")
            
            # Offer option to initialize schema
            if st.button("Initialize Database Schema"):
                from schema_init import initialize_database_schema
                try:
                    initialize_database_schema(engine)
                    st.success("Schema initialized successfully! Please refresh this page.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error initializing schema: {e}")
        
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        st.info("""
        Please check your database configuration parameters in the Supabase dashboard:
        1. Go to Project Settings > Database
        2. Find the connection parameters or connection string
        3. Make sure the DATABASE_URL or individual parameters are correctly set
        """)

if __name__ == "__main__":
    main()