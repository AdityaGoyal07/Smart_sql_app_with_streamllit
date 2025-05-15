import streamlit as st
import pandas as pd
from datetime import datetime

def init_history():
    """Initialize the history in session state if not already present"""
    if "history" not in st.session_state:
        st.session_state.history = []

def add_to_history(action_type, content, error=None):
    """Add an action to the history"""
    # Initialize history if not already done
    init_history()
    
    # Create history entry
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action_type": action_type,
        "content": content,
        "error": error
    }
    
    # Add to history
    st.session_state.history.append(entry)
    
    # Limit history size (keep last 100 entries)
    if len(st.session_state.history) > 100:
        st.session_state.history = st.session_state.history[-100:]

def get_history():
    """Get the history from session state"""
    # Initialize history if not already done
    init_history()
    
    # Return history
    return st.session_state.history

def clear_history():
    """Clear the history"""
    st.session_state.history = []

def history_to_dataframe():
    """Convert history to a pandas DataFrame"""
    history = get_history()
    
    if not history:
        return pd.DataFrame(columns=["timestamp", "action_type", "content", "error"])
    
    return pd.DataFrame(history)

def render_history_ui():
    """Render the UI for the history page"""
    st.header("Action History")
    st.write("View your recent actions and queries")
    
    # Get history
    history = get_history()
    
    if not history:
        st.info("No history available yet. Your actions will be recorded here.")
        return
    
    # Convert to DataFrame for easier filtering and display
    df = history_to_dataframe()
    
    # Filter options
    st.subheader("Filter History")
    col1, col2 = st.columns(2)
    
    with col1:
        action_types = ["All"] + sorted(df["action_type"].unique().tolist())
        selected_action_type = st.selectbox("Action Type", action_types)
    
    with col2:
        show_errors_only = st.checkbox("Show Errors Only")
    
    # Apply filters
    filtered_df = df.copy()
    
    if selected_action_type != "All":
        filtered_df = filtered_df[filtered_df["action_type"] == selected_action_type]
    
    if show_errors_only:
        filtered_df = filtered_df[filtered_df["error"].notnull()]
    
    # Display history
    st.subheader("History Entries")
    
    if filtered_df.empty:
        st.info("No entries match the selected filters.")
    else:
        # Sort by timestamp (newest first)
        filtered_df = filtered_df.sort_values("timestamp", ascending=False)
        
        # Display entries
        for _, row in filtered_df.iterrows():
            with st.expander(f"{row['timestamp']} - {row['action_type']}"):
                st.write(f"**Timestamp:** {row['timestamp']}")
                st.write(f"**Action Type:** {row['action_type']}")
                
                # Display content in code block if it's a query
                if row['action_type'] in ['query_executed', 'query_failed', 'ai_query_generated']:
                    st.code(row['content'])
                else:
                    st.write(f"**Content:** {row['content']}")
                
                # Display error if present
                if pd.notnull(row['error']):
                    st.error(f"**Error:** {row['error']}")
    
    # Clear history button
    if st.button("Clear History"):
        clear_history()
        st.success("History cleared.")
        st.rerun()
    
    # Download history
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download History as CSV",
        data=csv,
        file_name="action_history.csv",
        mime='text/csv',
    )
