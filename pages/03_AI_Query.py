import streamlit as st
from auth import init_page
from ai_query import render_ai_query_ui

# Initialize page with auth and session
cookies, user_id = init_page(
    page_title="AI Query - SQL Tool",
    page_icon="🤖"
)

# Page content
st.title("AI SQL Query Generator")
st.write("""
Convert natural language questions into SQL queries using AI.
Simply describe what data you want to retrieve, and the AI will generate the appropriate SQL query.
""")

st.image(
    "https://pixabay.com/get/g19823c1bb9806f78f906736423734b60811213372fac80b7ede6373fc1551508cd97269ec0cf9b2f4118285ec1081cdc63f711ff8411c2c61312bbf9159bfb90_1280.jpg", 
    caption="AI-Powered Query Generation"
)

# Render the AI query UI
render_ai_query_ui()
