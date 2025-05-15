import re
import duckdb
def sanitize_table_name(filename: str) -> str:
    """Sanitize filenames to be SQL-safe table names (alphanumeric + underscore only)"""
    name = filename.rsplit('.', 1)[0]
    name = re.sub(r'[^\w]+', '_', name)
    return name.strip('_').lower()

def sanitize_column_name(col_name: str) -> str:
    """Sanitize column names to be SQL-safe (alphanumeric + underscore only)"""
    return re.sub(r'[^\w]+', '_', col_name).strip('_').lower()

def sanitize_identifier(name: str) -> str:
    """
    Ensure a string is a valid SQL identifier.
    Prevents SQL injection by allowing only alphanumeric and underscores.
    """
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"Invalid identifier: {name}")
    return name

def clean_sql_output(sql_text: str) -> str:
    """Remove markdown-style triple backticks and whitespace around SQL"""
    sql_text = re.sub(r"^```sql\s*", "", sql_text, flags=re.IGNORECASE)
    sql_text = re.sub(r"```$", "", sql_text)
    return sql_text.strip()

def load_file_as_table(file_objs, supabase):
    """
    Load one or more files into DataFrames and sanitize for SQL usage.

    Args:
        file_objs (dict or list of dict): File metadata dict(s) with keys 'file_name' and 'full_path'.
        supabase: Initialized Supabase storage client.

    Returns:
        dict: {sanitized_table_name: DataFrame}
    """
    from file_manager import get_signed_url  # local import to avoid circular imports
    import pandas as pd
    import streamlit as st

    # Normalize single dict input to a list
    if isinstance(file_objs, dict):
        file_objs = [file_objs]

    tables = {}

    for file_obj in file_objs:
        try:
            file_name = file_obj['file_name']
            full_path = file_obj['full_path']
        except (TypeError, KeyError):
            st.warning(f"Invalid file object: {file_obj}")
            continue

        table_name = sanitize_table_name(file_name)
        signed_url = get_signed_url(full_path, supabase)
        if not signed_url:
            st.warning(f"Could not get URL for {file_name}")
            continue

        try:
            if file_name.endswith('.csv'):
                df = pd.read_csv(signed_url)
            elif file_name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(signed_url)
            else:
                st.warning(f"Unsupported file format: {file_name}")
                continue

            # Sanitize column names
            df.columns = [sanitize_column_name(c) for c in df.columns]
            tables[table_name] = df

        except Exception as e:
            st.warning(f"Error loading {file_name}: {e}")

    return tables
