import os
from openai import OpenAI


class LLMClient:
    def __init__(self, api_key: str, model: str = "nvidia/nemotron-3-nano-30b-a3b:free"):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.model = model

    def generate(self, system_prompt: str, user_message: str) -> str:
        """Generate a response using the LLM."""
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.output_text


def create_client(model: str = "nvidia/nemotron-3-nano-30b-a3b:free") -> LLMClient:
    """Create an LLMClient using environment variables."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is required")
    return LLMClient(api_key, model)
