import streamlit as st
import duckdb
import pandas as pd

from file_manager import init_supabase_storage, list_files
from sql_utils import sanitize_identifier, load_file_as_table
from history import add_to_history
from notifications import add_notification

DISPLAY_TO_INTERNAL = {
    "From PC": "pc",
    "Google Drive": "google_drive",
    "Scheduled Uploads": "scheduled",
}

def render_query_builder_ui(user_id: str, bucket: str = "pc"):
    supabase = init_supabase_storage()
    files = list_files(supabase=supabase, upload_type=bucket)

    if not files:
        st.warning("No files found.")
        return

    selected_files = st.multiselect("Select files to build query from", [f['file_name'] for f in files])
    if not selected_files:
        st.info("Please select at least one file.")
        return

    # Load files as DuckDB tables
    con = duckdb.connect()
    table_dataframes = {}
    columns_dict = {}

    for fname in selected_files:
        file_obj = next((f for f in files if f['file_name'] == fname), None)
        if not file_obj:
            continue

        loaded_tables = load_file_as_table(file_obj, supabase)
        for table_name, df in loaded_tables.items():
            if df is not None:
                con.register(table_name, df)
                table_dataframes[table_name] = df
                columns_dict[table_name] = df.columns.tolist()
                st.caption(f"Loaded `{fname}` as table `{table_name}`")

    selected_tables = list(table_dataframes.keys())
    if not selected_tables:
        st.error("No tables could be loaded.")
        return

    # Column selection
    st.subheader("Select Columns to Display")
    all_columns = []
    for t in selected_tables:
        all_columns.extend([f"{t}.{col}" for col in columns_dict[t]])

    selected_columns = st.multiselect("Select columns", all_columns, default=all_columns[:10])

    # Join logic
    join_ops = ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN"]
    if "join_conditions" not in st.session_state:
        st.session_state.join_conditions = []

    if len(selected_tables) > 1:
        st.subheader("Join Tables")
        for i in range(len(selected_tables) - 1):
            t1 = selected_tables[i]
            t2 = selected_tables[i + 1]
            st.markdown(f"**Join `{t1}` ↔ `{t2}`**")

            join_col1 = st.selectbox(f"Join column from `{t1}`", columns_dict[t1], key=f"jc1_{i}")
            join_col2 = st.selectbox(f"Join column from `{t2}`", columns_dict[t2], key=f"jc2_{i}")
            join_op = st.selectbox("Join type", join_ops, key=f"joinop_{i}")

            if len(st.session_state.join_conditions) <= i:
                st.session_state.join_conditions.append({})
            st.session_state.join_conditions[i] = {
                "left_table": t1,
                "right_table": t2,
                "left_col": join_col1,
                "right_col": join_col2,
                "operator": join_op
            }
    else:
        st.session_state.join_conditions = []

    # WHERE Conditions
    st.subheader("WHERE Conditions")
    if "conditions" not in st.session_state:
        st.session_state.conditions = []

    for i, cond in enumerate(st.session_state.conditions):
        col1, col2, col3, col4 = st.columns([3, 2, 3, 1])
        with col1:
            st.text(cond["column"])
        with col2:
            st.text(cond["operator"])
        with col3:
            st.text(cond["value"])
        with col4:
            if st.button("Remove", key=f"rm_cond_{i}"):
                st.session_state.conditions.pop(i)
                st.rerun()

    with st.expander("Add Condition"):
        cond_col = st.selectbox("Column", all_columns, key="cond_col")
        cond_op = st.selectbox("Operator", ["=", "!=", ">", "<", ">=", "<=", "LIKE", "IN", "IS NULL", "IS NOT NULL"])
        cond_val = "" if cond_op in ["IS NULL", "IS NOT NULL"] else st.text_input("Value", key="cond_val")

        if st.button("Add Condition"):
            if cond_op not in ["IS NULL", "IS NOT NULL"] and not cond_val:
                st.warning("Enter value for the condition.")
            else:
                st.session_state.conditions.append({
                    "column": cond_col,
                    "operator": cond_op,
                    "value": cond_val
                })
                st.rerun()

    # Order & Limit
    st.subheader("Order & Limit")
    order_col = st.selectbox("Order by", ["None"] + all_columns)
    order_dir = st.selectbox("Order Direction", ["ASC", "DESC"])
    limit = st.number_input("Limit", min_value=1, value=100)

    # Generate SQL
    st.subheader("Generated SQL")

    try:
        sanitized_tables = [sanitize_identifier(t) for t in selected_tables]
    except Exception as e:
        st.error(f"Invalid table name: {e}")
        return

    query = f"SELECT {', '.join(selected_columns) if selected_columns else '*'} FROM {sanitized_tables[0]}"

    for jc in st.session_state.join_conditions:
        lt = sanitize_identifier(jc["left_table"])
        rt = sanitize_identifier(jc["right_table"])
        lc = sanitize_identifier(jc["left_col"])
        rc = sanitize_identifier(jc["right_col"])
        op = jc["operator"]
        query += f" {op} {rt} ON {lt}.{lc} = {rt}.{rc}"

    if st.session_state.conditions:
        where_clauses = []
        for cond in st.session_state.conditions:
            col = cond["column"]
            op = cond["operator"]
            val = cond["value"]

            t, c = col.split(".")
            t = sanitize_identifier(t)
            c = sanitize_identifier(c)

            if op in ["IS NULL", "IS NOT NULL"]:
                where_clauses.append(f"{t}.{c} {op}")
            elif op == "IN":
                values = ", ".join([f"'{v.strip()}'" for v in val.split(",")])
                where_clauses.append(f"{t}.{c} IN ({values})")
            elif op == "LIKE":
                where_clauses.append(f"{t}.{c} LIKE '%{val}%'")
            else:
                try:
                    float(val)
                    where_clauses.append(f"{t}.{c} {op} {val}")
                except:
                    where_clauses.append(f"{t}.{c} {op} '{val}'")

        query += " WHERE " + " AND ".join(where_clauses)

    if order_col != "None":
        t, c = order_col.split(".")
        query += f" ORDER BY {sanitize_identifier(t)}.{sanitize_identifier(c)} {order_dir}"

    query += f" LIMIT {limit}"

    st.code(query, language="sql")

    if st.button("Run Query"):
        try:
            result = con.execute(query).fetchdf()
            st.success("Query executed successfully.")
            st.dataframe(result)

            csv = result.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "query_results.csv", mime="text/csv")

            add_to_history("query_executed", query)
            add_notification("Query Success", "SQL query ran successfully.", level="success")
        except Exception as e:
            st.error(f"Query failed: {e}")
            add_to_history("query_failed", query, error=str(e))
            add_notification("Query Failed", f"Query error: {e}", level="error")
