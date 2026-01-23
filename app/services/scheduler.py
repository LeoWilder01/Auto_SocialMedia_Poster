import asyncio
from datetime import datetime
from typing import Callable, Awaitable

from app.database import SessionLocal
from app.config import config
from app.services.notion import create_reader
from app.services.rag import get_rag_service
from app.models.post import NotionPage


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
    Creates a post and sends for approval.
    """
    from app.routes.posts import create_post
    from app.database import SessionLocal

    print(f"Notion page changed: {page_id}")
    print("Creating post for approval...")

    # Note: This creates a post request, but the approval flow
    # is synchronous and waits for Telegram response.
    # For a fully async flow, you'd need to queue the post creation.
    db = SessionLocal()
    try:
        # For now, just notify via Telegram that content changed
        from app.services.telegram import create_approver
        approver = create_approver()
        await approver.bot.send_message(
            approver.chat_id,
            f"Notion page updated!\n\nPage ID: {page_id}\n\nUse the API to create a post:\nPOST /posts/create/{page_id}"
        )
    finally:
        db.close()
