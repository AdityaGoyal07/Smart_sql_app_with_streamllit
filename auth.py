import streamlit as st
import re
import time
from supabase import create_client, Client
from datetime import datetime , date
from notifications import add_notification
from utils import get_db_connection
from sqlalchemy import text
import os
from streamlit_cookies_manager import EncryptedCookieManager

# Supabase Auth Configuration
try:
    AUTH_SUPABASE_URL = st.secrets["supabase_auth"]["URL"]
    AUTH_SUPABASE_KEY = st.secrets["supabase_auth"]["KEY"]
except:
    AUTH_SUPABASE_URL = os.getenv("AUTH_SUPABASE_URL")
    AUTH_SUPABASE_KEY = os.getenv("AUTH_SUPABASE_KEY")

# Development mode flag to bypass authentication checks
DEV_MODE = False

@st.cache_resource
def init_auth() -> Client:
    if not AUTH_SUPABASE_URL or not AUTH_SUPABASE_KEY:
        raise ValueError("Supabase URL and Key must be provided")
    return create_client(str(AUTH_SUPABASE_URL), str(AUTH_SUPABASE_KEY))

def _is_valid_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

def _is_valid_password(password: str) -> bool:
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"[a-z]", password) and
        re.search(r"\d", password) and
        re.search(r"[^\w\s]", password)
    )

def store_user_session(user_id, email, access_token, refresh_token):
    try:
        engine = get_db_connection()
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO user_sessions (user_id, email, access_token, refresh_token, created_at, last_active)
                VALUES (:user_id, :email, :access_token, :refresh_token, NOW(), NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    email = EXCLUDED.email,
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    last_active = NOW()
            """), {
                "user_id": user_id,
                "email": email,
                "access_token": access_token,
                "refresh_token": refresh_token
            })
            conn.commit()
    except Exception as e:
        print(f"Failed to store user session: {e}")

def restore_session_from_cookies(cookies):
    access_token = cookies.get("access_token")
    refresh_token = cookies.get("refresh_token")
    if access_token and refresh_token:
        try:
            supabase = init_auth()
            supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            time.sleep(0.3)
            user_response = supabase.auth.get_user()
            if user_response.user:
                st.session_state.authenticated = True
                st.session_state.user_id = user_response.user.id
                st.session_state.user_email = user_response.user.email
                st.session_state.access_token = access_token
                st.session_state.refresh_token = refresh_token
                store_user_session(user_response.user.id, user_response.user.email, access_token, refresh_token)
        except Exception as e:
            print(f"Failed to restore session from cookies: {e}")

def logout(cookies=None):
    try:
        supabase = init_auth()
        supabase.auth.sign_out()
    except Exception as e:
        st.error(f"Error during logout: {e}")

    for key in ['authenticated', 'user_id', 'user_email', 'access_token', 'refresh_token', 'notifications']:
        st.session_state.pop(key, None)

    if cookies:
        cookies["access_token"] = ""
        cookies["refresh_token"] = ""
        cookies.save()

    add_notification("Logged Out", "You have been successfully logged out.")
    
#main session persistence
def restore_and_verify_session():
    from utils import initialize_session_state
    from notifications import init_notifications

    initialize_session_state()

    cookie_password = st.secrets["cookies"]["pwd"]
    cookies = EncryptedCookieManager(prefix="queryvista/", password=cookie_password)

    if not cookies.ready():
        st.stop()

    init_notifications()

    if "session_restored" not in st.session_state:
        restore_session_from_cookies(cookies)
        st.session_state.session_restored = True

    return cookies


def get_user_id():
    return st.session_state.get("user_id", None)

def is_authenticated():
    return True if DEV_MODE else st.session_state.get("authenticated", False)

def toggle_dev_mode():
    global DEV_MODE
    DEV_MODE = not DEV_MODE
    message = "Authentication checks are now bypassed" if DEV_MODE else "Authentication checks are now enforced"
    add_notification("Dev Mode Toggled", message)
    return DEV_MODE

def is_dev_mode():
    return DEV_MODE

def auth_page():
    st.title("Authentication")
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"

    cookie_password = st.secrets["cookies"]["pwd"]
    cookies = EncryptedCookieManager(prefix="queryvista/", password=cookie_password)
    if not cookies.ready():
        st.stop()

    if st.session_state.auth_mode == "login":
        st.subheader("Login")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if not email or not password:
                st.error("Please enter both email and password")
                return

            try:
                supabase = init_auth()
                response = supabase.auth.sign_in_with_password({"email": email, "password": password})

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

                add_notification("Login Successful", f"Welcome back, {email}!")
                st.rerun()

            except Exception as e:
                if "Invalid login credentials" in str(e):
                    st.error("Invalid email or password")
                else:
                    st.error(f"Login failed: {str(e)}")

        st.write("Don't have an account?")
        if st.button("Sign up here"):
            st.session_state.auth_mode = "signup"
            st.rerun()

    elif st.session_state.auth_mode == "signup":
        st.subheader("Create an Account")

        full_name = st.text_input("Full Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone Number", max_chars=10)
        dob = st.date_input("Date of Birth",min_value=date(1990,1,1), max_value=datetime.today(),key="signup_dob")

        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")

        if phone and not re.fullmatch(r"^\d{10}$", phone):
            st.warning("Phone number must be exactly 10 digits.")

        def calculate_password_strength(pw):
            return sum([
                len(pw) >= 8,
                bool(re.search(r"[a-z]", pw)),
                bool(re.search(r"[A-Z]", pw)),
                bool(re.search(r"\d", pw)),
                bool(re.search(r"[^\w\s]", pw))
            ])

        if password:
            strength = calculate_password_strength(password)
            st.progress(strength / 5)
            labels = ["Very Weak", "Weak", "Moderate", "Strong", "Very Strong"]
            st.caption(f"Password Strength: {labels[strength - 1] if strength else 'Very Weak'}")

        if st.button("Sign Up"):
            if not all([full_name, email, dob, password, confirm_password]):
                st.error("Please fill in all required fields.")
                return

            if not _is_valid_email(email):
                st.error("Please enter a valid email address.")
                return

            if phone and not re.fullmatch(r"^\d{10}$", phone):
                st.error("Phone number must be exactly 10 digits.")
                return

            if not _is_valid_password(password):
                st.error("Password must be at least 8 characters long and include: uppercase, lowercase, digit, and special character.")
                return

            if password != confirm_password:
                st.error("Passwords do not match.")
                return

            try:
                supabase = init_auth()
                response = supabase.auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": {
                        "data": {
                            "full_name": full_name,
                            "phone": phone,
                            "dob": str(dob)
                        }
                    }
                })

                if response.user:
                    engine = get_db_connection()
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO metadata_users (uid, email, full_name, phone, dob, created_at)
                            VALUES (:uid, :email, :full_name, :phone, :dob, NOW())
                        """), {
                            "uid": response.user.id,
                            "email": email,
                            "full_name": full_name,
                            "phone": phone,
                            "dob": str(dob)
                        })
                        conn.commit()

                    login_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.authenticated = True

                    if login_response.user:
                        st.session_state.user_id = login_response.user.id
                        st.session_state.user_email = login_response.user.email
                    if login_response.session:
                        st.session_state.access_token = login_response.session.access_token
                        st.session_state.refresh_token = login_response.session.refresh_token
                        cookies["access_token"] = login_response.session.access_token
                        cookies["refresh_token"] = login_response.session.refresh_token
                        cookies.save()

                    store_user_session(
                        st.session_state.user_id,
                        st.session_state.user_email,
                        st.session_state.access_token,
                        st.session_state.refresh_token
                    )

                    st.success("Account created successfully! You're now logged in.")
                    add_notification("Account Created", "Your account has been created successfully.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to create account.")

            except Exception as e:
                if "already registered" in str(e).lower():
                    st.error("This email is already registered. Please log in instead.")
                else:
                    st.error(f"Signup failed: {str(e)}")

        st.write("Already have an account?")
        if st.button("Login here"):
            st.session_state.auth_mode = "login"
            st.rerun()

def login_form():
    st.info("Please use the authentication page to log in")
    st.button("Go to authentication page")

def signup_form():
    st.info("Please use the authentication page to sign up")
    st.button("Go to authentication page")
    
def init_page(page_title="QueryVista", page_icon="🔐", layout="wide"):
    import streamlit as st
    from notifications import init_notifications
    from auth_redirect import check_auth_and_redirect

    st.set_page_config(page_title=page_title, page_icon=page_icon, layout=layout)

    cookies = restore_and_verify_session()

    if not check_auth_and_redirect():
        st.stop()

    init_notifications()
    user_id = get_user_id()
    return cookies, user_id
