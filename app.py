from contextlib import AsyncExitStack
import json
import gradio as gr
import asyncio
import logging
import threading
import os
from configuration import Configuration
from mcp_manager import MCPManager
from navigationagent import NavigationAgent
from pageanalysisagent import PageAnalysisAgent
from conversationagent import ConversationAgent
from taskplanner import TaskPlanner
from llm_client import LocalQwenLLMClient, ChatGPTLLMClient
from task_storage import TaskStorage
from automation_task import AutomationTask

chatmanager = None
task_planner = None
exit_stack = None
task_storage = None
loop = None

# Handlers
def configure_credentials(action):
    return f"{action} setup done ✅"

def setup_channels():
    return "Started listening to Gmail ✅"

def setup_tasks():
    process_message("navigate to github.com")
    process_message("Find sign in button on the page")
    process_message("Click sign in button")
    process_message("Find username input box on the page")
    process_message("Click on username input box to make sure it is in focus")
    process_message("Slowly fill in username as vasiliy@live.com into username input box that is currently in focus")

    process_message("Find password input box on the page")
    process_message("Click on password input box to make sure it is in focus")
    github_password = os.environ.get("GITHUB_PASSWORD", "")
    process_message("Slowly fill in password as " + github_password + " into password input box that is currently in focus")

    process_message("Find sign in button on the page")
    process_message("Click sign in button") 
    return "GitHub task setup complete ✅"

def monitor_tasks():
    return "No tasks are setup."

def process_message(command):
    global loop, chatmanager
    if not loop or not chatmanager:
        return "Error: System not initialized"
    
    if not command.strip():
        return "Please enter a command"
    
    try:
        # Schedule the coroutine on the event loop and wait for result
        future = asyncio.run_coroutine_threadsafe(
            chatmanager.process_message(command), loop
        )
        # Wait for result with timeout
        result = future.result(timeout=210)
        return result
    except asyncio.TimeoutError:
        return f"Error: Command timed out, command: {command}"
    except Exception as e:
        logging.error(f"Error in process_message: {e}")
        return f"Error: {str(e)}"

# Tab content functions
def render_tab(tab, command_input=""):
    if tab == "Configure credentials":
        return (
            "Configure credentials",
            gr.update(visible=True), gr.update(visible=True),
            gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            "", gr.update(visible=False)
        )
    elif tab == "Setup channels":
        return (
            "Setup channels",
            gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=True), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            "", gr.update(visible=False)
        )
    elif tab == "Setup tasks":
        return (
            "Setup automation tasks",
            gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            "", gr.update(visible=True)
        )
    elif tab == "Monitor tasks":
        return (
            "Monitor tasks",
            gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            monitor_tasks(), gr.update(visible=False)
        )
    elif tab == "Test MCP":
        return (
            "Test MCP",
            gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=True), gr.update(visible=True),
            "", gr.update(visible=False)
        )

def handle_submit_task(name, description):
    info_is_missing = task_planner.check_for_missing_information(description)
    if info_is_missing:
        return (
            gr.update(value=task_planner.prepare_question(), visible=True),
            gr.update(value="", visible=True),
            gr.update(visible=True),
            gr.update(visible=False)
        )
    else:
        task = task_planner.prepare_plan(id="new", name=name, task_description=description)
        task_storage.addTask(task)
        return (
            gr.update(value="Task submitted successfully!", visible=True),
            gr.update(value="", visible=False),
            gr.update(visible=False),
            gr.update(visible=False)
        )
    
def create_interface():
    with gr.Blocks() as demo:
        tabs = ["Configure credentials", "Setup channels", "Setup tasks", "Monitor tasks", "Test MCP"]
        gr.Markdown("## MCP Control Panel")

        selected_tab = gr.Dropdown(tabs, label="Navigation", value="Monitor tasks")
        tab_title = gr.Markdown("Monitor tasks")

        result_output = gr.Textbox(label="Result", interactive=False, visible=False)

        # Buttons for each tab
        setup_gmail_btn = gr.Button("Setup Gmail", visible=False)
        setup_github_btn = gr.Button("Setup GitHub", visible=False)
        listen_gmail_btn = gr.Button("Listen to Gmail", visible=False)
        setup_github_task_btn = gr.Button("Setup GitHub Task", visible=False)
        test_input = gr.Textbox(label="Command to send to MCP", visible=False)
        send_command_btn = gr.Button("Send Command", visible=False)

        # --- Setup Tasks Tab UI ---
        with gr.Column(visible=False) as setup_tasks_tab:
            gr.Markdown("### Existing Tasks")
            # List of tasks with placeholder edit buttons
            def get_task_table():
                global task_storage
                if task_storage is None:
                    return []
                return [
                    [task.name, task.description or "", "Edit"] for task in task_storage.listTasks()
                ]
            task_list = gr.Dataframe(
                headers=["Name", "Description", "Edit"],
                datatype=["str", "str", "str"],
                interactive=False,
                value=get_task_table(),
                elem_id="task-list"
            )
            gr.Markdown("---")
            gr.Markdown("### Define New Task")
            new_task_name = gr.Textbox(label="Task Name", interactive=True)
            new_task_json = gr.Textbox(label="Task JSON", interactive=False)
            new_task_description = gr.Textbox(label="Task Description", interactive=True)
            submit_task_btn = gr.Button("Submit Information")

            popup_response_text = gr.Textbox(label="Agent Question", visible=False, interactive=False)
            popup_user_input = gr.Textbox(label="Your Answer", visible=False, interactive=True)
            popup_answer_btn = gr.Button("Answer", visible=False)

            submit_task_btn.click(
                fn=handle_submit_task,
                inputs=[new_task_name, new_task_description],
                outputs=[
                    popup_response_text,
                    popup_user_input,
                    popup_answer_btn,
                    result_output
                ]
            )

        # --- Setup Tasks Tab Logic ---
        # Update Task JSON when name or description changes
        def update_task_json(name, description):
            import json
            task = AutomationTask(id="new", name=name, description=description)
            return json.dumps(task.to_dict(), indent=2)
        new_task_name.change(fn=update_task_json, inputs=[new_task_name, new_task_description], outputs=new_task_json)
        new_task_description.change(fn=update_task_json, inputs=[new_task_name, new_task_description], outputs=new_task_json)

        # Bindings
        selected_tab.change(fn=render_tab, inputs=[selected_tab],
                            outputs=[tab_title,
                                    setup_gmail_btn, setup_github_btn,
                                    listen_gmail_btn, setup_github_task_btn,
                                    test_input, send_command_btn,
                                    result_output,
                                    setup_tasks_tab])

        setup_gmail_btn.click(fn=lambda: configure_credentials("Gmail"), outputs=result_output)
        setup_github_btn.click(fn=lambda: configure_credentials("GitHub"), outputs=result_output)
        listen_gmail_btn.click(fn=setup_channels, outputs=result_output)
        setup_github_task_btn.click(fn=setup_tasks, outputs=result_output)
        send_command_btn.click(fn=process_message, inputs=test_input, outputs=result_output)

        # Handler for "Answer" button: append user input to new_task_description
        def handle_answer(user_answer, current_description):
            if not user_answer:
                return current_description
            new_statement = task_planner.process_answer(user_answer)
            return current_description + "\n" + new_statement

        popup_answer_btn.click(
            fn=handle_answer,
            inputs=[popup_user_input, new_task_description],
            outputs=new_task_description
        ).then(
            fn=handle_submit_task,
            inputs=[new_task_name, new_task_description],
            outputs=[
                popup_response_text,
                popup_user_input,
                popup_answer_btn,
                result_output
            ]
        ).then(
            fn=get_task_table,
            inputs=[],
            outputs=task_list
        )

        test_input.submit(fn=process_message, inputs=test_input, outputs=result_output)
        
    return demo

async def async_init(loop):
    global chatmanager, exit_stack, task_storage, task_planner
    
    logging.info("Initializing async components...")

    config = Configuration()
    server_config = config.load_config("servers_config.json")
    exit_stack = AsyncExitStack()

    servers = [
        MCPManager(name, srv_config, exit_stack)
        for name, srv_config in server_config["mcpServers"].items()
    ]
    llm_client = ChatGPTLLMClient(config.llm_api_key)
    navigation_agent = NavigationAgent(servers, llm_client)
    page_analysis_agent = PageAnalysisAgent(llm_client)
    chatmanager = ConversationAgent(llm_client, navigation_agent, page_analysis_agent)
    task_planner = TaskPlanner(loop, llm_client)
    task_storage = TaskStorage()
    task_storage.initialize()
    await navigation_agent.initialize()
    await page_analysis_agent.initialize()
    await chatmanager.initialize()

    logging.info("Async initialization complete")

async def cleanup():
    """Cleanup function to be called on shutdown"""
    global chatmanager, exit_stack
    
    logging.info("Starting cleanup...")
    
    if chatmanager:
        try:
            await chatmanager.cleanup()
        except Exception as e:
            logging.error(f"Error during chat manager cleanup: {e}")
    
    if exit_stack:
        try:
            await exit_stack.aclose()
            logging.info("Exit stack closed successfully")
        except Exception as e:
            logging.error(f"Error closing exit stack: {e}")
    
    logging.info("Cleanup complete")

async def run_app():
    """Run the application with async lifecycle management"""
    global loop

    try:
        loop = asyncio.get_event_loop()

        # Initialize async components
        await async_init(loop)

        # Create and configure Gradio interface
        demo = create_interface()
        demo.queue()
        
        # Start Gradio in a separate thread but keep this event loop running

        gradio_ready = threading.Event()
        
        # Start Gradio in a separate thread
        def start_gradio():
            try:
                demo.launch(share=False, server_name="127.0.0.1", server_port=7861)
                gradio_ready.set()
            except Exception as e:
                logging.error(f"Error starting Gradio: {e}")
                gradio_ready.set()  # Set event even on error to avoid hanging
        
        gradio_thread = threading.Thread(target=start_gradio, daemon=True)
        gradio_thread.start()
        
        # Wait a bit for Gradio to start
        await asyncio.sleep(2)
        
        logging.info("Gradio server started, keeping event loop alive...")
               
        # Keep the event loop alive
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logging.info("Received shutdown signal")
            
    except Exception as e:
        logging.error(f"Error in main application: {e}")
        raise
    finally:
        # Cleanup
        await cleanup()

if __name__ == "__main__":    
    # Run the application
    try:
        asyncio.run(run_app())
    except KeyboardInterrupt:
        logging.info("Application shutdown requested")
    except Exception as e:
        logging.error(f"Application error: {e}")
        raise
