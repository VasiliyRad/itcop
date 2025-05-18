# streamlit_app.py
import streamlit as st
from task_manager import add_task, complete_task, get_tasks
from main import run_onboarding
import time

st.set_page_config(page_title="IT Automation", layout="wide")
st.title("🧠 IT Task Automation Agent")

# New task input
with st.sidebar:
    st.header("🚀 Launch New Task")
    username = st.text_input("Username to onboard")
    if st.button("Run Onboarding"):
        task = add_task("user_onboarding", username)
        st.success(f"Task #{task['id']} created for {username}")

# Show tasks
st.subheader("📋 Tasks")
tasks = get_tasks()

for task in tasks:
    with st.expander(f"#{task['id']} - {task['username']} - {task['status']}"):
        st.write(f"**Type:** {task['type']}")
        st.write(f"**Started:** {task['started_at']}")
        if task["status"] == "pending":
            if st.button(f"Run Task #{task['id']}", key=f"run_{task['id']}"):
                with st.spinner("Running agent..."):
                    result = run_onboarding(task["username"])
                    complete_task(task["id"], result)
                    st.success("Task completed")
        else:
            st.code(task["result"], language="markdown")
            feedback = st.text_input(f"Feedback for Task #{task['id']}", key=f"fb_{task['id']}")
            if feedback:
                st.success(f"✅ Feedback saved: {feedback}")

