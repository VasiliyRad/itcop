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
from transformers import AutoModelForCausalLM, AutoTokenizer

import concurrent.futures
from abc import ABC, abstractmethod

class LLMConfig:
    REMOTE_TIMEOUT = 60.0
    LOCAL_TIMEOUT = 180

class LLMClient(ABC):
    """Base class for LLM clients."""

    def __init__(self, api_key: str = None) -> None:
        self.api_key: Optional[str] = api_key
        self.thinking_pattern = r'<think>.*?</think>'
        self.json_code_block_pattern = r'```json\s*(.*?)\s*```'
        self.verbose_logging: bool = True
        self.tool_log_file: str = "tool.log"
        self.cache_file: str = "cache.json"
        try:
            with open(self.cache_file, "r") as f:
                self.cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.cache = {}

    def _is_error_response(self, response: str) -> bool:
        """Check if response indicates an error that shouldn't be cached."""
        # Check for specific timeout error from LocalQwenLLMClient
        if response.startswith("error: model.generate timed out"):
            return True
        return False
    
    def get_response(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        """Get a response from the LLM provider, using cache if available."""
        cache_key = json.dumps({"system_prompt": system_prompt, "messages": messages}, sort_keys=True)
        if cache_key in self.cache:
            logging.info("Cache hit for request.")
            return self.cache[cache_key]
        else:
            logging.info("Cache miss for request. Calling get_response_from_LLM.")
            response = self.get_response_from_LLM(system_prompt, messages)
            if not self._is_error_response(response):
                self.cache[cache_key] = response
            try:
                with open(self.cache_file, "w") as f:
                    json.dump(self.cache, f)
            except Exception as e:
                logging.error(f"Failed to write cache to disk: {e}")
            return response

    @abstractmethod
    def llm_version(self) -> str:
        """Report name and version of the LLM"""
        pass

    @abstractmethod
    def get_response_from_LLM(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        """Get a response from the LLM provider (no cache)."""
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
    def __init__(self, api_key: str = None) -> None:
        super().__init__(api_key)
        self.model_name = "claude-3-7-sonnet-20250219"

    def llm_version(self) -> str:
        return self.model_name

    def get_max_tool_response_length(self) -> int:
        return 8000
    
    def include_tool_results_in_history(self) -> bool:
        return True

    def get_response_from_LLM(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
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
            "model": self.model,
            "max_tokens": 4096,
            "temperature": 0.7,
            "top_p": 1.0,
            "system": system_prompt,
            "messages": structured_messages,
        }

        timeout = httpx.Timeout(LLMConfig.REMOTE_TIMEOUT)

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
    """LLM client for local Qwen (from huggingface)."""

    def __init__(self, api_key: str = None, model_name: str = "Qwen/Qwen3-8B") -> None:
        super().__init__(api_key)
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype="auto",
            device_map="auto"
        )
        logging.info(f"Loaded model and tokenizer for {self.model_name}")

    def llm_version(self) -> str:
        return self.model_name

    def get_max_tool_response_length(self) -> int:
        return 16000
    
    def include_tool_results_in_history(self) -> bool:
        return True

    def get_response_from_LLM(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        input_messages = [system_prompt] + messages

        logging.info(f"Getting response from local LLM. Input:")
        for message in input_messages:
            logging.info(f"role: {message['role']}, content: {message['content'][:300]}")

        text = self.tokenizer.apply_chat_template(
            input_messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=True # Switches between thinking and non-thinking modes. Default is True.
        )
        logging.info(f"Tokenized input text")
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self.model.generate,
                    **model_inputs,
                    max_new_tokens=2048
                )
                generated_ids = future.result(timeout=LLMConfig.LOCAL_TIMEOUT)
            logging.info(f"Got response from LLM")
        except concurrent.futures.TimeoutError:
            logging.error("model.generate timed out after 180 seconds")
            return "error: model.generate timed out after 180 seconds"
        output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()
        try:
            # rindex finding 151668 (</think>)
            index = len(output_ids) - output_ids[::-1].index(151668)
            logging.info(f"Found </think> token at index: {index}")
        except ValueError:
            index = 0
            logging.info(f"</think> token not found in the output.")
        
        thinking_content = self.tokenizer.decode(output_ids[:index], skip_special_tokens=True).strip("\n")
        logging.info(f"LLM response with thinking pattern: {thinking_content}")
        content = self.tokenizer.decode(output_ids[index:], skip_special_tokens=True).strip("\n")
        logging.info(f"LLM response: {content}")
        return content

class LocalQwenOlamaLLMClient(LLMClient):
    """LLM client for local Qwen (from olama)."""
    def __init__(self, api_key: str = None, model_name: str = "qwen3:8b") -> None:
        super().__init__(api_key)
        self.model_name = model_name

    def llm_version(self) -> str:
        return self.model_name

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
            response: ChatResponse = chat(model=self.model_name, messages=input_messages, options={'timeout': LLMConfig.LOCAL_TIMEOUT})
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

    def __init__(self, api_key: str = None) -> None:
        super().__init__(api_key)
        self.delay: float = 0.0  # Rate limiting delay
        self.model_name = "gpt-4.1"

    def llm_version(self) -> str:
        return self.model_name
    
    # chatgpt cheap pricing tier limit: 8000
    def get_max_tool_response_length(self) -> int:
        return 8000
    
    # leads to error if included
    def include_tool_results_in_history(self) -> bool:
        return False

    def parse_delay(self, header_value):
    # Parses delay value with support for different time units.
    # Supports: 's' (seconds), 'ms' (milliseconds), 'm' (minutes)
        header_value = header_value.strip().lower()
    
        if header_value.endswith('ms'):
            # Milliseconds - convert to seconds
            return float(header_value[:-2]) / 1000.0
        elif header_value.endswith('m'):
            # Minutes - convert to seconds
            return float(header_value[:-1]) * 60.0
        elif header_value.endswith('s'):
            # Seconds
            return float(header_value[:-1])
        else:
            # Default to seconds if no unit specified
            return float(header_value)

    def get_response_from_LLM(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
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
            "model": self.model_name,  # or "gpt-4-turbo", "gpt-3.5-turbo", etc.
            "messages": structured_messages,
            "max_tokens": 4096,
            "temperature": 0.7,
            "top_p": 1.0
        }

        timeout = httpx.Timeout(LLMConfig.REMOTE_TIMEOUT)

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
                                self.delay = self.parse_delay(header_value)
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
