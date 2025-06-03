import logging
import httpx
import time
import random
import json
import re
from ollama import chat
from ollama import ChatResponse
from typing import Optional
from pydantic import BaseModel, Field
from pydantic.networks import HttpUrl

from abc import ABC, abstractmethod

class LLMClient(ABC):
    """Base class for LLM clients."""

    def __init__(self, api_key: str = None) -> None:
        self.api_key: Optional[str] = api_key
        self.delay: float = 0.0  # Delay in seconds for rate limiting
        self.thinking_pattern = r'<think>.*?</think>'
        self.json_code_block_pattern = r'```json\s*(.*?)\s*```'
        self.verbose_logging: bool = True
        self.tool_log_file: str = "tool.log"

    @abstractmethod
    def get_response(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        """Get a response from the LLM provider."""
        pass

    @abstractmethod
    def get_max_tool_response_length(self) -> int:
        """Get the maximum length of tool response."""
        return 8000

    @abstractmethod
    def include_tool_results_in_history(self) -> bool:
        """Check if tool results should be included in conversation history."""
        return True
    
    def clean_response(self, response: str) -> str:
        """Clean response by removing JSON code block tags and other formatting."""
        cleaned_response = response
                        
        # Remove thinking patterns
        cleaned_response = re.sub(self.thinking_pattern, '', cleaned_response, flags=re.DOTALL)
        
        # Remove ```json and ``` tags, keeping only the content inside
        cleaned_response = re.sub(self.json_code_block_pattern, r'\1', cleaned_response, flags=re.DOTALL)

        return cleaned_response.strip()

    def append_tool_response(self, response: str, conversation: list[dict[str, str]]) -> list[dict[str, str]]:
        """Append tools response to messages."""
        if (len(response) > self.get_max_tool_response_length()):
            logging.info(f"Tool response is longer than {self.get_max_tool_response_length()} characters, truncating")
        if (self.verbose_logging):
            logging.info("Writing tool response to log file")   
            with open(self.tool_log_file, "w") as file:
                file.write(response)
        response = response[:self.get_max_tool_response_length()]
        
        if (self.include_tool_results_in_history()):
            # Include tool result in conversation history
            conversation.append({"role": "system", "content": response})
            messages = conversation
        else:
            messages = conversation + [{"role": "system", "content": response}]
        return messages

class ClaudeLLMClient(LLMClient):
    """LLM client for Anthropic Claude."""

    def get_max_tool_response_length(self) -> int:
        return 8000
    
    def include_tool_results_in_history(self) -> bool:
        return True

    def get_response(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        url = "https://api.anthropic.com/v1/messages"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        # Claude expects a single 'system' prompt and a list of user/assistant turns
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

class LocalQwenLLMClient(LLMClient):
    """LLM client for local Qwen (Ollama)."""

    def get_max_tool_response_length(self) -> int:
        return 16000
    
    def include_tool_results_in_history(self) -> bool:
        return True

    def get_response(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        input_messages = [system_prompt] + messages

        logging.info(f"Getting response from local LLM. Input:")
        for message in input_messages:
            logging.info(f"role: {message['role']}, content: {message['content'][:300]}")

        try:
            # model='qwen3:32b', model='qwen3:8b', model='llama3.2'
            response: ChatResponse = chat(model='qwen3:8b', messages=input_messages, options={'timeout': 120})
        except Exception as e:
            logging.error(f"Exception when running local model: {e}")
            return "error!"

        raw_response = response['message']['content']
        cleaned_text = self.clean_response(raw_response)

        if (cleaned_text != raw_response):
            logging.info(f"LLM response with thinking pattern: {raw_response}")
        elif 'error' in raw_response:
            logging.error(f"LLM response contains 'error': {raw_response}")

        return cleaned_text.strip()

class ChatGPTLLMClient(LLMClient):
    """LLM client for OpenAI ChatGPT."""

    # chatgpt cheap pricing tier limit: 8000
    def get_max_tool_response_length(self) -> int:
        return 8000
    
    # leads to error if included
    def include_tool_results_in_history(self) -> bool:
        return False

    def get_response(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        structured_messages = []

        # Extract system message and format messages list accordingly
        for message in messages + [system_prompt]:
            role = message["role"]
            content = message["content"]
            structured_messages.append({"role": role, "content": content})

        payload = {
            "model": "gpt-4o",  # or "gpt-4-turbo", "gpt-3.5-turbo", etc.
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
                    cleaned_text = self.clean_response(data["choices"][0]["message"]["content"])
                    return cleaned_text

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
