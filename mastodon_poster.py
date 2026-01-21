import os
import requests


class MastodonPoster:
    def __init__(self, access_token: str, instance_url: str = "https://mastodon.social"):
        self.access_token = access_token
        self.instance_url = instance_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {access_token}",
        }

    def upload_media(self, image_data: bytes, filename: str = "image.webp") -> str:
        """
        Upload an image to Mastodon.

        Args:
            image_data: The image as bytes
            filename: The filename to use

        Returns:
            The media_id to use when posting
        """
        # Use v1 API (synchronous) instead of v2 (async)
        url = f"{self.instance_url}/api/v1/media"

        files = {
            "file": (filename, image_data, "image/webp"),
        }

        response = requests.post(url, headers=self.headers, files=files)
        response.raise_for_status()
        return response.json()["id"]

    def post(self, content: str, visibility: str = "public", media_ids: list = None) -> dict:
        """
        Post a status to Mastodon.

        Args:
            content: The text content of the post (max 500 chars for most instances)
            visibility: One of "public", "unlisted", "private", "direct"
            media_ids: Optional list of media IDs to attach

        Returns:
            The created status as a dict
        """
        url = f"{self.instance_url}/api/v1/statuses"

        data = [
            ("status", content),
            ("visibility", visibility),
        ]

        if media_ids:
            for media_id in media_ids:
                data.append(("media_ids[]", media_id))

        response = requests.post(url, headers=self.headers, data=data)
        response.raise_for_status()
        return response.json()

    def verify_credentials(self) -> dict:
        """Verify the access token is valid and return account info."""
        url = f"{self.instance_url}/api/v1/accounts/verify_credentials"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()


def create_poster() -> MastodonPoster:
    """Create a MastodonPoster using environment variables."""
    access_token = os.environ.get("MASTODON_ACCESS_TOKEN")
    if not access_token:
        raise ValueError("MASTODON_ACCESS_TOKEN environment variable is required")

    instance_url = os.environ.get("MASTODON_INSTANCE_URL", "https://mastodon.social")
    return MastodonPoster(access_token, instance_url)
