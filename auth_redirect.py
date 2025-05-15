import streamlit as st
from auth import is_authenticated

def check_auth_and_redirect():
    """
    Check if user is authenticated, and if not, show a login button
    that redirects to the login page.
    
    Returns True if the user is authenticated, False otherwise.
    """
    if not is_authenticated():
        st.warning("You need to be logged in to access this feature.")
        
        # Add login button
        if st.button("Login / Sign Up", use_container_width=True):
            st.switch_page("pages/06_Login.py")
        
        # Add home button
        if st.button("Back to Home", use_container_width=True):
            st.switch_page("app.py")
            
        return False
    
    return True
