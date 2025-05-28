import logging
import httpx
import time
import random
import json
from typing import Optional
from pydantic import BaseModel, Field
from pydantic.networks import HttpUrl

class LLMClient:
    """Manages communication with the LLM provider."""

    def __init__(self, api_key: str) -> None:
        self.api_key: str = api_key
        self.delay: float = 0.0  # Delay in seconds for rate limiting

    def get_response_claude(self, messages: list[dict[str, str]]) -> str:
        url = "https://api.anthropic.com/v1/messages"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        # Claude expects a single 'system' prompt and a list of user/assistant turns
        system_prompt = None
        structured_messages = []

        for message in messages:
            role = message["role"]
            content = message["content"]
            if role == "system":
                system_prompt = content
            else:
                structured_messages.append({"role": role, "content": content})

        payload = {
            "model": "claude-3-7-sonnet-20250219",
            "max_tokens": 4096,
            "temperature": 0.7,
            "top_p": 1.0,
            "system": system_prompt,
            "messages": structured_messages,
        }

        timeout = httpx.Timeout(60.0) 

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["content"][0]["text"]

        except httpx.RequestError as e:
            error_message = f"Error getting Claude response: {str(e)}"
            logging.error(error_message)

            if isinstance(e, httpx.HTTPStatusError):
                status_code = e.response.status_code
                logging.error(f"Status code: {status_code}")
                logging.error(f"Response details: {e.response.text}")

            return (
                f"I encountered an error: {error_message}. "
                "Please try again or rephrase your request."
            )
        
    def get_response(self, messages: list[dict[str, str]]) -> str:
        url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        structured_messages = []

        # Extract system message and format messages list accordingly
        for message in messages:
            role = message["role"]
            content = message["content"]
            structured_messages.append({"role": role, "content": content})

        payload = {
            "model": "gpt-4",  # or "gpt-4-turbo", "gpt-3.5-turbo", etc.
            "messages": structured_messages,
            "max_tokens": 4096,
            "temperature": 0.7,
            "top_p": 1.0
        }

        timeout = httpx.Timeout(60.0) 

        for attempt in range(4):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, headers=headers, json=payload)
                    response.raise_for_status()

                    self.delay = 0.0  # Reset delay on successful response 
                    # Log rate limit headers
                    for header_name, header_value in response.headers.items():
                        if header_name.lower().startswith('x-ratelimit'):
                            logging.info(f"Rate limit header: {header_name}: {header_value}")
                            if (header_name.lower() == 'x-ratelimit-reset-tokens'):
                                self.delay = float(header_value.rstrip('s'))
                                logging.info(f"Rate limit reset delay set to {self.delay:.1f} seconds")
                
                    data = response.json()
                    return data["choices"][0]["message"]["content"]

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < 3:

                    if self.delay > 0:
                        wait_time = self.delay
                        logging.warning(f"Rate limited (429), waiting {wait_time:.1f}s before retry...")
                        self.delay = 0.0  # Reset delay after using it
                    else:
                        wait_time = random.uniform(10, 20)
                        logging.warning(f"Rate limited (429), waiting {wait_time:.1f}s before retry...")

                    time.sleep(wait_time)
                    continue
                elif e.response.status_code == 400:
                    # Log input messages for debugging 400 Bad Request errors
                    with open("bad_request.json", "w") as f:
                        json.dump(payload, f, indent=4)
                    logging.error(f"400 Bad Request. Check bad_request.json to inspect input messages.")
                    raise
                else:
                    # Re-raise for other status codes or final attempt
                    raise

            except httpx.RequestError as e:
                error_message = f"Error getting ChatGPT response: {str(e)}"
                logging.error(error_message)

                if isinstance(e, httpx.HTTPStatusError):
                    status_code = e.response.status_code
                    logging.error(f"Status code: {status_code}")
                    logging.error(f"Response details: {e.response.text}")

                return (
                    f"I encountered an error: {error_message}. "
                    "Please try again or rephrase your request."
                )
