import streamlit as st
import duckdb
import os
from openai import OpenAI
import sqlparse

from history import add_to_history
from notifications import add_notification
from file_manager import init_supabase_storage, list_files
from sql_utils import (
    sanitize_table_name,
    sanitize_column_name,
    clean_sql_output,
    load_file_as_table,
)

# OpenAI Initialization
try:
    OPENAI_API_KEY = st.secrets["openapi"]["api_key"]
except:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "default_key")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

DISPLAY_TO_INTERNAL = {
    "From PC": "pc",
    "Google Drive": "google_drive",
    "Scheduled Uploads": "scheduled",
}

def generate_sql_from_text(question, tables_info):
    try:
        schema_info = ""
        for table, columns in tables_info.items():
            schema_info += f"Table: {table}\nColumns:\n"
            for col in columns:
                schema_info += f"- {col['name']} ({col['type']})\n"
            schema_info += "\n"

        prompt = f"""Convert this natural language question to a valid SQL query.

Database Schema:
{schema_info}

Question: "{question}"

Respond with only the SQL query (PostgreSQL syntax).
"""

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert SQL developer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
        )

        raw_sql = response.choices[0].message.content
        sql_query = clean_sql_output(raw_sql)

        add_to_history("ai_query_generated", sql_query)
        st.session_state.ai_queries = st.session_state.get("ai_queries", 0) + 1
        return sql_query, None

    except Exception as e:
        add_to_history("ai_query_failed", question, error=str(e))
        return None, str(e)

def render_ai_query_ui():
    st.subheader("1️⃣ Select File Source")
    supabase = init_supabase_storage()
    upload_types_display = list(DISPLAY_TO_INTERNAL.keys())
    selected_display = st.selectbox("Select Upload Source", upload_types_display)
    selected_type = DISPLAY_TO_INTERNAL[selected_display]

    files = list_files(supabase=supabase, upload_type=selected_type)
    if not files:
        st.warning("No files found for this source.")
        return

    st.subheader("2️⃣ Select Files to Use")
    selected_files = st.multiselect("Choose one or more files", [f['file_name'] for f in files])

    if not selected_files:
        st.warning("Please select at least one file.")
        return

    table_dataframes = {}  # {table_name: df}
    tables_info = {}

    for fname in selected_files:
        file_obj = next((f for f in files if f['file_name'] == fname), None)
        if not file_obj:
            st.warning(f"Could not find metadata for {fname}")
            continue

        tables = load_file_as_table(file_obj, supabase)
        for table_name, df in tables.items():
            if df is not None:
                table_dataframes[table_name] = df
                tables_info[table_name] = [
                    {"name": sanitize_column_name(col), "type": str(df[col].dtype)}
                    for col in df.columns
                ]
                st.caption(f"Loaded `{file_obj['file_name']}` as **{table_name}**")
                st.dataframe(df.head())


    if not table_dataframes:
        st.error("Failed to load any selected files.")
        return

    st.subheader("3️⃣ Ask Your Question in Natural Language")
    examples = [
        "Show top 10 rows from all tables",
        "Join the tables and show common records",
        "List all rows from table1 where column x > 1000",
    ]
    for example in examples:
        if st.button(example):
            st.session_state.ai_query_input = example
            st.rerun()

    question = st.text_area("Your question", value=st.session_state.get("ai_query_input", ""), height=100)

    if st.button("Generate SQL"):
        if not question:
            st.warning("Enter a question.")
            return
        with st.spinner("Generating SQL..."):
            sql_query, error = generate_sql_from_text(question, tables_info)
            if error:
                st.error(error)
            else:
                formatted_sql = sqlparse.format(sql_query, reindent=True, keyword_case="upper")
                st.session_state.generated_sql = formatted_sql
                st.session_state.ai_query_input = question
                add_notification("SQL Generated", "Query generated successfully!")
                st.rerun()

    if "generated_sql" in st.session_state:
        st.subheader("4️⃣ Generated SQL")
        edited_sql = st.text_area("Review or Edit SQL", value=st.session_state.generated_sql, height=150)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Execute Query"):
                try:
                    con = duckdb.connect()
                    for table_name, df in table_dataframes.items():
                        con.register(table_name, df)

                    result = con.execute(edited_sql).fetchdf()
                    st.success("Query executed successfully!")
                    add_to_history("query_executed", edited_sql)
                    st.session_state.queries_run = st.session_state.get("queries_run", 0) + 1

                    st.subheader("Query Results")
                    st.dataframe(result)

                    csv = result.to_csv(index=False).encode("utf-8")
                    st.download_button("Download Results as CSV", csv, "ai_query_results.csv", mime="text/csv")
                except Exception as e:
                    st.error(f"Query execution failed: {e}")
                    add_to_history("query_failed", edited_sql, error=str(e))

        with col2:
            if st.button("Clear Query"):
                del st.session_state.generated_sql
                st.rerun()