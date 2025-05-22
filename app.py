import streamlit as st
from configuration import Configuration
from mcp_client import Server, LLMClient, ChatSession

# Tab titles
tabs = ["Configure credentials", "Setup channels", "Setup tasks", "Monitor tasks", "Test MCP"]

# Handle query params to default to "Monitor tasks"
params = st.query_params
default_tab = params.get("tab", ["Monitor tasks"])[0]
default_index = tabs.index(default_tab) if default_tab in tabs else 3

# Tab selection
selected_tab = st.selectbox("Navigation", tabs, index=default_index)
params.tab=selected_tab

# Tab content logic
if selected_tab == "Configure credentials":
    st.header("Configure credentials")
    if st.button("Setup Gmail"):
        st.success("Done")
    if st.button("Setup GitHub"):
        st.success("Done")

elif selected_tab == "Setup channels":
    st.header("Setup channels")
    if st.button("Listen to Gmail"):
        st.success("Done")

elif selected_tab == "Setup tasks":
    st.header("Setup tasks")
    if st.button("Setup GitHub task"):
        st.success("Done")

elif selected_tab == "Monitor tasks":
    st.header("Monitor tasks")
    st.info("No tasks are setup")

elif selected_tab == "Test MCP":
    st.header("Test MCP")

    # Initialize config, servers, LLM client, and chat session only once
    if "chat_session" not in st.session_state:
        config = Configuration()
        server_config = config.load_config("servers_config.json")
        servers = [
            Server(name, srv_config)
            for name, srv_config in server_config["mcpServers"].items()
        ]
        llm_client = LLMClient(config.llm_api_key)
        chat_session = ChatSession(servers, llm_client)
        st.session_state.chat_session = chat_session
        st.session_state.conversation = []
    else:
        chat_session = st.session_state.chat_session

    # Display conversation so far
    if "conversation" not in st.session_state:
        st.session_state.conversation = []

    for msg in st.session_state.conversation:
        if msg["role"] == "user":
            st.markdown(f"**You:** {msg['content']}")
        elif msg["role"] == "assistant":
            st.markdown(f"**Assistant:** {msg['content']}")
        elif msg["role"] == "system":
            st.info(msg["content"])

    # User input
    user_input = st.text_input("Type your message:", key="user_input")
    if st.button("Send") and user_input.strip():
        # Process message and update conversation
        updated_convo = chat_session.process_message_sync(user_input)
        st.session_state.conversation = updated_convo
        st.rerun()
