import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # API Security
    API_KEY: str = os.getenv("API_KEY", "")

    # Notion
    NOTION_API_KEY: str = os.getenv("NOTION_API_KEY", "")

    # OpenRouter (LLM)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

    # Mastodon
    MASTODON_ACCESS_TOKEN: str = os.getenv("MASTODON_ACCESS_TOKEN", "")
    MASTODON_INSTANCE_URL: str = os.getenv("MASTODON_INSTANCE_URL", "https://mastodon.social")

    # Replicate (Image Generation)
    REPLICATE_API_TOKEN: str = os.getenv("REPLICATE_API_TOKEN", "")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///posts.db")


config = Config()
