import os
import asyncio
from dotenv import load_dotenv

from notion_reader import create_reader
from llm_client import create_client
from mastodon_poster import create_poster
from image_generator import create_generator
from telegram_bot import request_approval, notify_posted


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


def generate_social_post(notion_content: str, page_title: str, tone: str = None) -> str:
    """Generate a social media post from Notion content."""
    llm = create_client()

    system_prompt = TONE_PROMPTS.get(tone, TONE_PROMPTS[None])

    user_message = f"""Create a social media post based on this content:

Title: {page_title}

Content:
{notion_content}"""

    return llm.generate(system_prompt, user_message)


async def approval_loop(post: str, page_content: str, page_title: str) -> tuple[str, bytes]:
    """
    Loop until user approves the post via Telegram.

    Returns:
        Tuple of (approved_post, image_data)
    """
    generator = create_generator()
    current_post = post

    while True:
        # Generate image for current post
        print("\nGenerating image...")
        image_data = generator.generate(current_post)
        print("Image generated!")

        # Send to Telegram for approval (with image)
        print("Sending to Telegram for approval...")
        result = await request_approval(current_post, image_data)

        if result["approved"]:
            return current_post, image_data

        # User rejected - regenerate with new tone
        tone = result["tone"]
        print(f"Regenerating with {tone} tone...")
        current_post = generate_social_post(page_content, page_title, tone)

        print("\nRegenerated Post:")
        print("=" * 40)
        print(current_post)
        print("=" * 40)


async def main_async():
    """Async main function."""
    # Load environment variables from .env file
    load_dotenv()

    # Get page ID from environment
    page_id = os.environ.get("NOTION_PAGE_ID")
    if not page_id:
        raise ValueError("NOTION_PAGE_ID environment variable is required")

    # Read from Notion
    print("Reading from Notion...")
    reader = create_reader()
    page_title = reader.get_page_title(page_id)
    page_content = reader.get_page_content(page_id)

    print(f"Page title: {page_title}")
    print(f"Content length: {len(page_content)} characters")
    print("-" * 40)

    # Generate initial social media post
    print("Generating social media post...")
    post = generate_social_post(page_content, page_title)

    print("\nGenerated Post:")
    print("=" * 40)
    print(post)
    print("=" * 40)
    print(f"\nCharacter count: {len(post)}/500")

    # Telegram approval loop
    approved_post, image_data = await approval_loop(post, page_content, page_title)

    # Upload and post to Mastodon
    print("\nUploading to Mastodon...")
    poster = create_poster()
    media_id = poster.upload_media(image_data)
    print(f"Image uploaded (media_id: {media_id})")

    print("Posting...")
    result = poster.post(approved_post, media_ids=[media_id])
    post_url = result.get('url')
    print(f"Posted successfully!")
    print(f"URL: {post_url}")

    # Notify via Telegram
    await notify_posted(post_url)

    return approved_post


def main():
    """Entry point - runs the async main function."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    main()
