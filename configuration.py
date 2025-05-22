import json
import os

class Configuration:
    def __init__(self):
        # Prefer environment variable, fallback to config file
        self.llm_api_key = os.environ.get("OPENAI_API_KEY", "")

    def load_config(self, path):
        with open(path, "r") as f:
            config = json.load(f)
        # If env var is not set, use value from config file
        if not self.llm_api_key:
            self.llm_api_key = config.get("llmApiKey", "")
        return config
