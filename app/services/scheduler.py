import asyncio
from datetime import datetime
from typing import Callable, Awaitable

from app.database import SessionLocal
from app.config import config
from app.services.notion import create_reader
from app.services.rag import get_rag_service
from app.models.post import NotionPage, Post


class NotionPoller:
    """Background service that polls Notion for changes."""

    def __init__(self, on_change_callback: Callable[[str], Awaitable[None]] = None):
        self.polling_interval = 3600  # 1 hour in seconds
        self.is_running = False
        self.on_change_callback = on_change_callback
        self.watched_pages = []  # List of page IDs to watch

    def add_page(self, page_id: str):
        """Add a page to watch for changes."""
        if page_id not in self.watched_pages:
            self.watched_pages.append(page_id)
            print(f"Now watching Notion page: {page_id}")

    def remove_page(self, page_id: str):
        """Remove a page from watch list."""
        if page_id in self.watched_pages:
            self.watched_pages.remove(page_id)

    async def check_for_changes(self) -> list[str]:
        """Check all watched pages for changes. Returns list of changed page IDs."""
        changed_pages = []
        reader = create_reader()
        db = SessionLocal()

        try:
            rag_service = get_rag_service(db)

            for page_id in self.watched_pages:
                try:
                    page_info = reader.get_page_info(page_id)

                    if rag_service.check_notion_changed(
                        page_id,
                        page_info["content"],
                        page_info["last_edited_time"]
                    ):
                        print(f"[{datetime.utcnow()}] Change detected in page: {page_id}")
                        changed_pages.append(page_id)

                        # Re-index the page
                        notion_page = db.query(NotionPage).filter(
                            NotionPage.page_id == page_id
                        ).first()

                        if notion_page:
                            chunks = rag_service.index_notion_page(notion_page, page_info["content"])
                            print(f"Re-indexed {chunks} chunks for page: {page_id}")

                except Exception as e:
                    print(f"Error checking page {page_id}: {e}")

        finally:
            db.close()

        return changed_pages

    async def poll_loop(self):
        """Main polling loop."""
        print(f"Notion poller started. Checking every {self.polling_interval} seconds.")

        # Add default page from config
        if config.NOTION_PAGE_ID:
            self.add_page(config.NOTION_PAGE_ID)

        while self.is_running:
            try:
                changed_pages = await self.check_for_changes()

                # Trigger callback for each changed page
                if self.on_change_callback:
                    for page_id in changed_pages:
                        try:
                            await self.on_change_callback(page_id)
                        except Exception as e:
                            print(f"Error in change callback for {page_id}: {e}")

            except Exception as e:
                print(f"Error in poll loop: {e}")

            # Wait for next interval
            await asyncio.sleep(self.polling_interval)

    async def start(self):
        """Start the polling loop."""
        if not self.is_running:
            self.is_running = True
            asyncio.create_task(self.poll_loop())
            print("Notion poller started")

    async def stop(self):
        """Stop the polling loop."""
        self.is_running = False
        print("Notion poller stopped")


# Global poller instance
_poller: NotionPoller = None


def get_poller() -> NotionPoller:
    """Get the global poller instance."""
    global _poller
    if _poller is None:
        _poller = NotionPoller()
    return _poller


async def on_notion_change(page_id: str):
    """
    Callback when a Notion page changes.
    Automatically creates a post and sends for Telegram approval.
    """
    from app.services.llm import create_client
    from app.services.image import create_generator
    from app.services.mastodon import create_poster
    from app.services.telegram import request_approval, notify_posted

    print(f"[AUTO-POST] Notion page changed: {page_id}")
    print("[AUTO-POST] Starting automatic post creation...")

    db = SessionLocal()
    try:
        # Read from Notion
        reader = create_reader()
        page_info = reader.get_page_info(page_id)
        page_title = page_info["title"]
        page_content = page_info["content"]

        print(f"[AUTO-POST] Page title: {page_title}")

        # Get or create NotionPage record
        notion_page = db.query(NotionPage).filter(NotionPage.page_id == page_id).first()
        if not notion_page:
            notion_page = NotionPage(page_id=page_id, title=page_title)
            db.add(notion_page)
            db.commit()
            db.refresh(notion_page)

        # Get RAG context
        rag_service = get_rag_service(db)
        rag_context = rag_service.get_context_for_query(page_content[:500], top_k=3)
        if rag_context:
            print(f"[AUTO-POST] Using RAG context ({len(rag_context)} chars)")

        # Generate post
        print("[AUTO-POST] Generating social media post...")
        llm = create_client()
        post_content = llm.generate_social_post(page_content, page_title, None, rag_context)
        print(f"[AUTO-POST] Generated post ({len(post_content)} chars)")

        # Create pending post in DB
        post = Post(
            content=post_content,
            status="pending",
            notion_page_id=notion_page.id
        )
        db.add(post)
        db.commit()
        db.refresh(post)

        # Generate image
        print("[AUTO-POST] Generating image...")
        generator = create_generator()
        image_data = generator.generate(post_content)

        # Telegram approval loop
        current_post = post_content
        while True:
            print("[AUTO-POST] Sending to Telegram for approval...")
            result = await request_approval(current_post, image_data)

            if result["approved"]:
                break

            # Regenerate with new tone
            new_tone = result["tone"]
            print(f"[AUTO-POST] Regenerating with {new_tone} tone...")
            current_post = llm.generate_social_post(page_content, page_title, new_tone, rag_context)

            # Regenerate image
            image_data = generator.generate(current_post)

            # Update post in DB
            post.content = current_post
            db.commit()

        # Post to Mastodon
        print("[AUTO-POST] Posting to Mastodon...")
        poster = create_poster()
        media_id = poster.upload_media(image_data)
        mastodon_result = poster.post(current_post, media_ids=[media_id])

        # Update post record
        post.content = current_post
        post.mastodon_url = mastodon_result.get("url")
        post.mastodon_id = mastodon_result.get("id")
        post.status = "posted"
        post.posted_at = datetime.utcnow()
        db.commit()

        # Notify via Telegram
        await notify_posted(post.mastodon_url)

        print(f"[AUTO-POST] Posted successfully: {post.mastodon_url}")

    except Exception as e:
        print(f"[AUTO-POST] Error: {e}")
        # Notify about error via Telegram
        try:
            from app.services.telegram import create_approver
            approver = create_approver()
            await approver.bot.send_message(
                approver.chat_id,
                f"Auto-post failed!\n\nPage: {page_id}\nError: {str(e)}"
            )
        except:
            pass

    finally:
        db.close()
