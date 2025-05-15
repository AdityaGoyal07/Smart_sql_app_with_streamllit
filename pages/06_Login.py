import streamlit as st
from auth import auth_page, is_authenticated
from notifications import init_notifications

# Set page config
st.set_page_config(
    page_title="Login - SQL Tool",
    page_icon="🔑",
    layout="wide"
)

# Initialize notifications
init_notifications()

# Main content
def main():
    if is_authenticated():
        st.success("You're already logged in!")
        
        # Provide option to go to home page
        if st.button("Go to Home Page", use_container_width=True):
            st.switch_page("app.py")
        
        # Provide option to go to file manager
        if st.button("Go to File Manager", use_container_width=True):
            st.switch_page("pages/04_File_Manager.py")
    else:
        # Center the login form
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.title("Login / Create Account")
            st.markdown("""
            ### Welcome to QueryVista
            
            Access all features by signing in to your account or creating a new one.
            """)
            
            # Show the login/signup form
            auth_page()
            
            # Add a button to go back to home
            st.markdown("---")
            if st.button("Back to Home", use_container_width=True):
                st.switch_page("app.py")

if __name__ == "__main__":
    main()
