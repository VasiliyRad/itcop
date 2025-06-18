# itcop

A simple automation and agent framework powered by LLMs (such as OpenAI's ChatGPT) and optionally local models via Hugging Face.

## Getting Started

Follow these steps to set up and run the project:

### 1. Install Python Requirements

Make sure you have Python 3.8+ installed. Python 3.13 is recommended. 
Then, install the required dependencies:

```bash
pip install -r requirements.txt
```

### 2. Set the OpenAI API Key

To use ChatGPT, you need to set the `OPENAI_API_KEY` environment variable with your OpenAI API key.

**On macOS/Linux:**
```bash
export OPENAI_API_KEY=your_openai_api_key_here
```

**On Windows (Command Prompt):**
```cmd
set OPENAI_API_KEY=your_openai_api_key_here
```

### 3. (Optional) Use a Local Model with Hugging Face

If you prefer to use a local model (e.g., Qwen) instead of OpenAI, you can install the Hugging Face CLI and download the model:

```bash
pip install huggingface_hub
huggingface-cli login
huggingface-cli download Qwen/Qwen3-8B
```

Replace `Qwen/Qwen3-8B` with your preferred model if needed.

---

You are now ready to run the project!