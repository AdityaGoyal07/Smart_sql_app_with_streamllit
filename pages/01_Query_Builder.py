import streamlit as st
from query_builder import render_query_builder_ui
from auth import init_page

cookies, user_id = init_page("Query Builder - SQL Tool", "📊")

st.title("SQL Query Builder")
st.write("""
Use this tool to build SQL queries using a visual interface. 
Select a table, columns, and add conditions to create your query.
""")

st.image(
    "https://pixabay.com/get/ga9a4c71f99519f90a673c3a87402dcfecc004a333a3cc4e5af30161b9188d68509bf57f805729c288169473b89f3efdaa8b2e0e58086b375c07df1c3828260f7_1280.jpg", 
    caption="Database Interface"
)

upload_source = st.selectbox("Choose source", ["From PC", "Google Drive", "Scheduled Uploads"])
source_key = {
    "From PC": "pc",
    "Google Drive": "google_drive",
    "Scheduled Uploads": "scheduled"
}[upload_source]

render_query_builder_ui(user_id, bucket=source_key)
