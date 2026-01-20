import os
import requests


class NotionReader:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

    def get_page(self, page_id: str) -> dict:
        """Fetch page metadata."""
        url = f"{self.base_url}/pages/{page_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_blocks(self, block_id: str) -> list:
        """Fetch all blocks (content) from a page or block."""
        url = f"{self.base_url}/blocks/{block_id}/children"
        all_blocks = []

        while url:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            all_blocks.extend(data.get("results", []))

            # Handle pagination
            if data.get("has_more"):
                next_cursor = data.get("next_cursor")
                url = f"{self.base_url}/blocks/{block_id}/children?start_cursor={next_cursor}"
            else:
                url = None

        return all_blocks

    def extract_text_from_block(self, block: dict) -> str:
        """Extract plain text from a single block."""
        block_type = block.get("type")
        if not block_type:
            return ""

        block_content = block.get(block_type, {})

        # Handle rich_text fields (most common)
        if "rich_text" in block_content:
            return "".join(
                rt.get("plain_text", "") for rt in block_content["rich_text"]
            )

        # Handle special block types
        if block_type == "child_page":
            return f"[Page: {block_content.get('title', '')}]"

        if block_type == "child_database":
            return f"[Database: {block_content.get('title', '')}]"

        return ""

    def get_page_content(self, page_id: str) -> str:
        """Get all text content from a page as a single string."""
        blocks = self.get_blocks(page_id)

        texts = []
        for block in blocks:
            text = self.extract_text_from_block(block)
            if text:
                texts.append(text)

        return "\n".join(texts)

    def get_page_title(self, page_id: str) -> str:
        """Get the title of a page."""
        page = self.get_page(page_id)
        properties = page.get("properties", {})

        # Title can be in different property names
        for prop_name, prop_value in properties.items():
            if prop_value.get("type") == "title":
                title_parts = prop_value.get("title", [])
                return "".join(t.get("plain_text", "") for t in title_parts)

        return "Untitled"


def create_reader() -> NotionReader:
    """Create a NotionReader using environment variables."""
    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        raise ValueError("NOTION_API_KEY environment variable is required")
    return NotionReader(api_key)
