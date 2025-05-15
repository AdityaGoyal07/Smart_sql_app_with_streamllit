import streamlit as st
from datetime import datetime

def init_notifications():
    """Initialize notifications in session state if not already present"""
    if "notifications" not in st.session_state:
        st.session_state.notifications = []

def add_notification(title, message, level="info"):
    """Add a notification to the session state"""
    # Initialize notifications if not already done
    init_notifications()
    
    # Create notification
    notification = {
        "title": title,
        "message": message,
        "level": level,  # info, success, warning, error
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "read": False
    }
    
    # Add to notifications
    st.session_state.notifications.append(notification)
    
    # Limit notifications (keep last 20)
    if len(st.session_state.notifications) > 20:
        st.session_state.notifications = st.session_state.notifications[-20:]

def mark_notification_as_read(index):
    """Mark a notification as read"""
    if "notifications" in st.session_state and 0 <= index < len(st.session_state.notifications):
        st.session_state.notifications[index]["read"] = True

def mark_all_notifications_as_read():
    """Mark all notifications as read"""
    if "notifications" in st.session_state:
        for notification in st.session_state.notifications:
            notification["read"] = True

def clear_notifications():
    """Clear all notifications"""
    st.session_state.notifications = []

def get_unread_notification_count():
    """Get the count of unread notifications"""
    if "notifications" not in st.session_state:
        return 0
    
    return sum(1 for notification in st.session_state.notifications if not notification["read"])

def show_notification(title, message, level="info"):
    """Show a notification and add it to history"""
    # Add notification to history
    add_notification(title, message, level)
    
    # Show notification based on level
    if level == "info":
        st.info(f"{title}: {message}")
    elif level == "success":
        st.success(f"{title}: {message}")
    elif level == "warning":
        st.warning(f"{title}: {message}")
    elif level == "error":
        st.error(f"{title}: {message}")

def render_notifications_ui():
    """Render the UI for notifications"""
    # Initialize notifications
    init_notifications()
    
    # Get notifications
    notifications = st.session_state.notifications
    
    if not notifications:
        st.info("No notifications available.")
        return
    
    # Display notifications
    st.subheader("Notifications")
    
    # Add buttons to manage notifications
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Mark All as Read"):
            mark_all_notifications_as_read()
            st.success("All notifications marked as read.")
            st.rerun()
    
    with col2:
        if st.button("Clear All Notifications"):
            clear_notifications()
            st.success("All notifications cleared.")
            st.rerun()
    
    # Display notifications in reverse order (newest first)
    for i, notification in enumerate(reversed(notifications)):
        # Use appropriate icon based on level
        icon = "ℹ️"  # Default info icon
        if notification["level"] == "success":
            icon = "✅"
        elif notification["level"] == "warning":
            icon = "⚠️"
        elif notification["level"] == "error":
            icon = "❌"
        
        # Display notification
        with st.expander(
            f"{icon} {notification['title']} ({notification['time']})",
            expanded=not notification["read"]
        ):
            st.write(f"**Message:** {notification['message']}")
            st.write(f"**Time:** {notification['time']}")
            st.write(f"**Level:** {notification['level']}")
            
            # Mark as read button
            if not notification["read"]:
                if st.button("Mark as Read", key=f"read_{i}"):
                    # We need to calculate the actual index in the list
                    actual_index = len(notifications) - 1 - i
                    mark_notification_as_read(actual_index)
                    st.success("Notification marked as read.")
                    st.rerun()
