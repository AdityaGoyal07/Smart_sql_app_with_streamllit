import streamlit as st
from auth import init_auth, store_user_session
from notifications import add_notification
from streamlit_cookies_manager import EncryptedCookieManager
import re

def login_page():
    st.title("🔐 Login to QueryVista")

    # Cookie setup
    cookie_password = st.secrets["cookies"]["pwd"]
    cookies = EncryptedCookieManager(prefix="queryvista/", password=cookie_password)
    if not cookies.ready():
        st.stop()

    email = st.text_input("📧 Email")
    password = st.text_input("🔒 Password", type="password")

    if st.button("Login"):
        if not email or not password:
            st.error("❌ Please enter both email and password.")
            return

        try:
            supabase = init_auth()
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if response.user:
                st.session_state.authenticated = True
                st.session_state.user_id = response.user.id
                st.session_state.user_email = response.user.email

                if response.session:
                    st.session_state.access_token = response.session.access_token
                    st.session_state.refresh_token = response.session.refresh_token
                    cookies["access_token"] = response.session.access_token
                    cookies["refresh_token"] = response.session.refresh_token
                    cookies.save()

                store_user_session(
                    st.session_state.user_id,
                    st.session_state.user_email,
                    st.session_state.access_token,
                    st.session_state.refresh_token
                )

                add_notification("✅ Login Successful", f"Welcome back, {email}!")
                st.rerun()

            else:
                st.error("❌ Login failed. Please check your credentials.")

        except Exception as e:
            if "Invalid login credentials" in str(e):
                st.error("❌ Invalid email or password.")
            else:
                st.error(f"⚠️ Login failed: {str(e)}")

    st.write("---")
    st.caption("Don't have an account?")
    if st.button("Create an Account"):
        st.session_state.auth_mode = "signup"
        st.rerun()
