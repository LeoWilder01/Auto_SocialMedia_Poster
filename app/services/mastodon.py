import requests

from app.config import config


class MastodonPoster:
    def __init__(self):
        self.access_token = config.MASTODON_ACCESS_TOKEN
        self.instance_url = config.MASTODON_INSTANCE_URL.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
        }

    def upload_media(self, image_data: bytes, filename: str = "image.webp") -> str:
        """Upload an image to Mastodon and return the media_id."""
        url = f"{self.instance_url}/api/v1/media"

        files = {
            "file": (filename, image_data, "image/webp"),
        }

        response = requests.post(url, headers=self.headers, files=files)
        response.raise_for_status()
        return response.json()["id"]

    def post(self, content: str, visibility: str = "public", media_ids: list = None) -> dict:
        """Post a status to Mastodon."""
        url = f"{self.instance_url}/api/v1/statuses"

        data = {
            "status": content,
            "visibility": visibility,
        }

        if media_ids:
            data["media_ids[]"] = media_ids

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
    """Create a MastodonPoster using config."""
    if not config.MASTODON_ACCESS_TOKEN:
        raise ValueError("MASTODON_ACCESS_TOKEN environment variable is required")
    return MastodonPoster()
