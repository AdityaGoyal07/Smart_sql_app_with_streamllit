import streamlit as st
import duckdb
import pandas as pd

from file_manager import init_supabase_storage, list_files
from sql_utils import sanitize_identifier, load_file_as_table
from history import add_to_history
from notifications import add_notification


def render_query_builder_ui(user_id: str, bucket: str = "pc"):
    st.info(f"Current source: `{bucket}`")

    supabase = init_supabase_storage()
    files = list_files(supabase=supabase, upload_type=bucket)

    if not files:
        st.warning("No files found for selected source.")
        return

    selected_files = st.multiselect("Select files to build query from", [f['file_name'] for f in files])
    if not selected_files:
        st.info("Please select at least one file.")
        return

    con = duckdb.connect()
    table_dataframes = {}
    columns_dict = {}

    st.subheader("Loaded Table Schema")

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

                with st.expander(f"📄 `{table_name}` Schema"):
                    st.write(df.head(5))

    selected_tables = list(table_dataframes.keys())
    if not selected_tables:
        st.error("No tables could be loaded.")
        return

    st.subheader("Select Columns")
    all_columns = list({col for cols in columns_dict.values() for col in cols})
    selected_columns = st.multiselect("Columns to display", all_columns, default=all_columns[:5])

    # --- Aggregate functions section with toggle and dynamic add/remove ---
    st.subheader("Apply Aggregate Functions (optional)")

    if st.checkbox("Apply Aggregate Functions"):
        if "agg_conditions" not in st.session_state:
            st.session_state.agg_conditions = []  # list of dicts {column, function}

        def add_agg_condition():
            st.session_state.agg_conditions.append({"column": None, "function": None})

        if st.button("➕ Add Aggregate Function"):
            add_agg_condition()

        aggregate_functions = ["COUNT", "SUM", "AVG", "MIN", "MAX"]

        remove_idx = None
        for i, agg_cond in enumerate(st.session_state.agg_conditions):
            cols = st.columns([3, 3, 1])
            with cols[0]:
                col_selected = st.selectbox(
                    f"Select column #{i + 1}",
                    selected_columns,
                    index=selected_columns.index(agg_cond["column"]) if agg_cond["column"] in selected_columns else 0,
                    key=f"agg_col_{i}",
                )
            with cols[1]:
                func_selected = st.selectbox(
                    f"Function #{i + 1}",
                    aggregate_functions,
                    index=aggregate_functions.index(agg_cond["function"]) if agg_cond["function"] in aggregate_functions else 0,
                    key=f"agg_func_{i}",
                )
            with cols[2]:
                if st.button("Remove", key=f"rm_agg_{i}"):
                    remove_idx = i

            st.session_state.agg_conditions[i]["column"] = col_selected
            st.session_state.agg_conditions[i]["function"] = func_selected

        if remove_idx is not None:
            st.session_state.agg_conditions.pop(remove_idx)
            st.rerun()
    else:
        st.session_state.agg_conditions = []

    # Build aggregate_selection dict from session state
    aggregate_selection = {}
    for agg_cond in st.session_state.get("agg_conditions", []):
        if agg_cond["column"] and agg_cond["function"]:
            aggregate_selection[agg_cond["column"]] = agg_cond["function"]

    # --- Joins ---
    join_ops = ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN"]
    if "join_conditions" not in st.session_state:
        st.session_state.join_conditions = []

    if len(selected_tables) > 1:
        st.subheader("Join Tables")
        for i in range(len(selected_tables) - 1):
            t1 = selected_tables[i]
            t2 = selected_tables[i + 1]
            st.markdown(f"**Join `{t1}` ↔ `{t2}`**")

            common_cols = list(set(columns_dict[t1]) & set(columns_dict[t2]))
            if not common_cols:
                st.warning(f"No common columns between `{t1}` and `{t2}`")
                continue

            join_col = st.selectbox("Join on column", common_cols, key=f"jc_{i}")
            join_op = st.selectbox("Join type", join_ops, key=f"joinop_{i}")

            if len(st.session_state.join_conditions) <= i:
                st.session_state.join_conditions.append({})

            st.session_state.join_conditions[i] = {
                "left_table": t1,
                "right_table": t2,
                "col": join_col,
                "operator": join_op,
            }
    else:
        st.session_state.join_conditions = []

    # --- WHERE conditions ---
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

    with st.expander("➕ Add Condition"):
        cond_col = st.selectbox("Column", all_columns, key="cond_col")
        cond_op = st.selectbox(
            "Operator",
            ["=", "!=", ">", "<", ">=", "<=", "LIKE", "IN", "IS NULL", "IS NOT NULL"],
        )
        cond_val = "" if cond_op in ["IS NULL", "IS NOT NULL"] else st.text_input("Value", key="cond_val")

        if st.button("Add Condition"):
            if cond_op not in ["IS NULL", "IS NOT NULL"] and not cond_val:
                st.warning("Enter value for the condition.")
            else:
                st.session_state.conditions.append(
                    {"column": cond_col, "operator": cond_op, "value": cond_val}
                )
                st.rerun()

    # --- ORDER & LIMIT ---
    st.subheader("Order & Limit")
    order_col = st.selectbox("Order by", ["None"] + all_columns)
    order_dir = st.selectbox("Order Direction", ["ASC", "DESC"])
    limit = st.number_input("Limit", min_value=1, value=100)

    # --- SQL Query Generation ---
    base_table = sanitize_identifier(selected_tables[0])

    select_parts = []
    group_by_cols = []

    # If aggregates chosen, show those aggregates for those columns
    # Columns without aggregate function will be grouped by
    if aggregate_selection:
        for col in selected_columns:
            col_id = sanitize_identifier(col)
            if col in aggregate_selection:
                func = aggregate_selection[col]
                select_parts.append(f"{func}({col_id}) AS {func.lower()}_{col_id}")
            else:
                # Non-aggregated columns must appear in GROUP BY
                select_parts.append(col_id)
                group_by_cols.append(col_id)
    else:
        # No aggregates, select all chosen columns as-is
        select_parts = [sanitize_identifier(col) for col in selected_columns]

    query = f"SELECT {', '.join(select_parts) if select_parts else '*'} FROM {base_table}"

    for jc in st.session_state.join_conditions:
        lt = sanitize_identifier(jc["left_table"])
        rt = sanitize_identifier(jc["right_table"])
        col = sanitize_identifier(jc["col"])
        op = jc["operator"]
        query += f" {op} {rt} ON {lt}.{col} = {rt}.{col}"

    if st.session_state.conditions:
        where_clauses = []
        for cond in st.session_state.conditions:
            col = sanitize_identifier(cond["column"])
            op = cond["operator"]
            val = cond["value"]

            if op in ["IS NULL", "IS NOT NULL"]:
                where_clauses.append(f"{col} {op}")
            elif op == "IN":
                values = ", ".join([f"'{v.strip()}'" for v in val.split(",")])
                where_clauses.append(f"{col} IN ({values})")
            elif op == "LIKE":
                where_clauses.append(f"{col} LIKE '%{val}%'")
            else:
                try:
                    float(val)
                    where_clauses.append(f"{col} {op} {val}")
                except:
                    where_clauses.append(f"{col} {op} '{val}'")

        query += " WHERE " + " AND ".join(where_clauses)

    if group_by_cols:
        query += " GROUP BY " + ", ".join(group_by_cols)

    if order_col != "None":
        query += f" ORDER BY {sanitize_identifier(order_col)} {order_dir}"

    query += f" LIMIT {limit}"

    st.subheader("Generated SQL")
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
