import streamlit as st
import pandas as pd
import duckdb

from auth import init_page
from notifications import init_notifications, add_notification
from file_manager import init_supabase_storage, list_files
from sql_utils import load_file_as_table, sanitize_identifier
from history import add_to_history

# --- Setup ---
cookies, user_id = init_page("Custom Query - SQL Tool", "📊")
init_notifications()

st.title("Custom SQL Query")
st.write("""
Write and execute custom SQL queries on your uploaded files (CSV) using DuckDB engine.
No database or write operations needed.
""")

# --- Select Source ---
upload_display = st.selectbox("Select upload source", ["From PC", "Google Drive", "Scheduled Uploads"])
UPLOAD_SOURCE_MAP = {
    "From PC": "pc",
    "Google Drive": "google_drive",
    "Scheduled Uploads": "scheduled"
}
upload_type = UPLOAD_SOURCE_MAP[upload_display]

# --- Load Files ---
supabase = init_supabase_storage()
files = list_files(supabase, upload_type)

if not files:
    st.warning("No files found in this source.")
    st.stop()

selected_files = st.multiselect("Select files to include in query", [f['file_name'] for f in files])
if not selected_files:
    st.info("Select at least one file to proceed.")
    st.stop()

# --- Load into DuckDB ---
con = duckdb.connect()
table_dataframes = {}

st.info("Loading selected files...")
for file_name in selected_files:
    file_obj = next((f for f in files if f['file_name'] == file_name), None)
    if not file_obj:
        continue
    loaded_tables = load_file_as_table(file_obj, supabase)
    for table_name, df in loaded_tables.items():
        con.register(table_name, df)
        table_dataframes[table_name] = df
        st.caption(f"Registered `{file_name}` as table `{table_name}`")

if not table_dataframes:
    st.error("No tables were registered successfully.")
    st.stop()

# --- Show Schema ---
with st.expander("📄 View Table Schemas"):
    for table_name, df in table_dataframes.items():
        st.write(f"### {table_name}")
        st.dataframe(pd.DataFrame({
            "Column Name": df.columns,
            "Data Type": [str(dtype) for dtype in df.dtypes]
        }))

# --- SQL Input ---
st.subheader("Enter SQL Query")
query = st.text_area("Write your SQL query below. You can reference the loaded tables.", height=200)

# --- Execute ---
if st.button("Execute Query"):
    if not query.strip():
        st.warning("Please enter a SQL query.")
        st.stop()

    try:
        with st.spinner("Running your query..."):
            if query.strip().upper().startswith("SELECT"):
                result_df = con.execute(query).fetchdf()
                st.success("Query executed successfully!")
                st.dataframe(result_df)

                csv = result_df.to_csv(index=False).encode("utf-8")
                st.download_button("Download Results as CSV", csv, "query_results.csv", mime="text/csv")

                add_to_history("query_executed", query)
                add_notification("Query Success", "Your custom SELECT query executed successfully.", level="success")
            else:
                con.execute(query)
                st.success("Non-SELECT query executed (e.g., CREATE TABLE, INSERT).")

                add_to_history("query_executed", query)
                add_notification("Non-SELECT Query Executed", "Your custom SQL query was executed.", level="success")

    except Exception as e:
        st.error(f"Query failed: {e}")
        add_to_history("query_failed", query, error=str(e))
        add_notification("Query Failed", f"Error: {e}", level="error")
