# tools/user_tools.py
from langchain.tools import tool
from playwright.sync_api import sync_playwright

@tool
def check_flight_status(airline="Alaska airlines", flight_number=1078) -> str:
    """Checks the flight status for a given airline and flight number."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Step 1: Navigate to the website
        page.goto("https://www.alaskaair.com")

        page.wait_for_load_state("networkidle")

        # Step 2: Click on the "Flight status" tab
        page.locator("#tab-status").click()

        page.wait_for_load_state("networkidle")

        # Step 3: Fill in "flight number" with 1078
        page.get_by_label("Flight number").fill("1078")

        page.wait_for_load_state("networkidle")

        # Step 4: Click the "Continue" button
        page.get_by_role("button", name="Continue").click()

        # Step 5: Wait for navigation or relevant result section to appear
        page.wait_for_load_state("networkidle")

        title = page.title()
        if (title == "Client Challenge"):
            page.wait_for_timeout(10000)

        # Step 6: Get the page content (you can pass this to an LLM)
        content = page.locator(".flight-container").inner_html()
        #content = page.content()

        # Optional: Print or save for inspection
        print(content[:1000])  # printing first 1000 chars

        browser.close()
    return content


@tool
def create_email_account(username: str) -> str:
    """Creates an email account for the user."""
    # Imagine calling an internal API here
    return f"Created email for {username}"

@tool
def add_to_slack(username: str) -> str:
    """Adds a user to Slack."""
    return f"Added {username} to Slack"

@tool
def provision_github(username: str) -> str:
    """Provisions a GitHub account."""
    return f"GitHub account provisioned for {username}"

