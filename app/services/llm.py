from openai import OpenAI

from app.config import config


TONE_PROMPTS = {
    None: """You are a social media content creator.
Based on the content provided, create an engaging social media post.
Keep it concise, engaging, and shareable.
Include relevant hashtags if appropriate.""",

    "casual": """You are a social media content creator with a casual, friendly voice.
Based on the content provided, create a fun, relaxed social media post.
Use conversational language, maybe some humor, and keep it light.
Include relevant hashtags if appropriate.""",

    "formal": """You are a professional social media content creator.
Based on the content provided, create a polished, professional social media post.
Use clear, professional language while remaining engaging.
Include relevant hashtags if appropriate.""",
}


class LLMClient:
    def __init__(self, model: str = "nvidia/nemotron-3-nano-30b-a3b:free"):
        self.client = OpenAI(
            api_key=config.OPENROUTER_API_KEY,
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

    def generate_social_post(self, notion_content: str, page_title: str, tone: str = None, rag_context: str = None) -> str:
        """Generate a social media post from Notion content with optional RAG context."""
        system_prompt = TONE_PROMPTS.get(tone, TONE_PROMPTS[None])

        # Build user message with optional RAG context
        user_message = f"""Create a social media post based on this content:

Title: {page_title}

Content:
{notion_content}"""

        if rag_context:
            user_message += f"""

---
Relevant context from knowledge base (use this to inform your post style and content):
{rag_context}
---"""

        return self.generate(system_prompt, user_message)


def create_client(model: str = "nvidia/nemotron-3-nano-30b-a3b:free") -> LLMClient:
    """Create an LLMClient using config."""
    if not config.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY environment variable is required")
    return LLMClient(model)
