import os
from dotenv import load_dotenv

from notion_reader import create_reader
from llm_client import create_client
from mastodon_poster import create_poster
from image_generator import create_generator


def generate_social_post(notion_content: str, page_title: str) -> str:
    """Generate a social media post from Notion content."""
    llm = create_client()

    system_prompt = """You are a social media content creator.
Based on the content provided, create an engaging social media post.
Keep it concise, engaging, and shareable.
Include relevant hashtags if appropriate."""

    user_message = f"""Create a social media post based on this content:

Title: {page_title}

Content:
{notion_content}"""

    return llm.generate(system_prompt, user_message)


def main():
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

    # Generate social media post
    print("Generating social media post...")
    post = generate_social_post(page_content, page_title)

    print("\nGenerated Post:")
    print("=" * 40)
    print(post)
    print("=" * 40)

    # Ask user if they want to post to Mastodon
    print(f"\nCharacter count: {len(post)}/500")
    user_input = input("\nPost to Mastodon? (y/n): ").strip().lower()

    if user_input == "y":
        # Generate image
        print("\nGenerating image...")
        generator = create_generator()
        image_data = generator.generate(post)
        print("Image generated!")

        # Upload image and post
        print("Uploading to Mastodon...")
        poster = create_poster()
        media_id = poster.upload_media(image_data)
        print(f"Image uploaded (media_id: {media_id})")

        print("Posting...")
        result = poster.post(post, media_ids=[media_id])
        print(f"Posted successfully!")
        print(f"URL: {result.get('url')}")
    else:
        print("Skipped posting.")

    return post


if __name__ == "__main__":
    main()
