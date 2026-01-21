import os
import re
import replicate


class ImageGenerator:
    def __init__(self):
        # Replicate uses REPLICATE_API_TOKEN env var automatically
        self.model = "sundai-club/my_snorlax:d659b33482657f5dd2ce1076377aa55a36248b80339bf5479de9aedd9723f93c"
        self.trigger_word = "snorlax"

    def extract_keywords(self, text: str, max_words: int = 5) -> str:
        """Extract key words from text to use in image prompt."""
        # Remove hashtags, URLs, and special characters
        clean_text = re.sub(r'#\w+', '', text)
        clean_text = re.sub(r'http\S+', '', clean_text)
        clean_text = re.sub(r'[^\w\s]', '', clean_text)

        # Get unique words, filter short ones
        words = clean_text.lower().split()
        keywords = []
        seen = set()

        # Skip common words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                      'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                      'could', 'should', 'may', 'might', 'can', 'this', 'that',
                      'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
                      'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
                      'by', 'from', 'as', 'into', 'through', 'about', 'out', 'up',
                      'down', 'off', 'over', 'under', 'again', 'further', 'then',
                      'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all',
                      'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
                      'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
                      'just', 'your', 'our', 'their', 'its', 'my'}

        for word in words:
            if len(word) > 3 and word not in seen and word not in stop_words:
                keywords.append(word)
                seen.add(word)
                if len(keywords) >= max_words:
                    break

        return ' '.join(keywords)

    def generate(self, post_text: str) -> bytes:
        """
        Generate an image based on post text.

        Args:
            post_text: The social media post text to base the image on

        Returns:
            Image data as bytes
        """
        # Build prompt with trigger word + extracted keywords
        keywords = self.extract_keywords(post_text)
        prompt = f"{self.trigger_word} {keywords}"

        print(f"Image prompt: {prompt}")

        output = replicate.run(
            self.model,
            input={
                "model": "dev",
                "prompt": prompt,
                "go_fast": False,
                "lora_scale": 1,
                "megapixels": "1",
                "num_outputs": 1,
                "aspect_ratio": "1:1",
                "output_format": "webp",
                "guidance_scale": 3,
                "output_quality": 80,
                "prompt_strength": 0.8,
                "extra_lora_scale": 1,
                "num_inference_steps": 28
            }
        )

        # Read image data from the output
        image_data = output[0].read()
        return image_data


def create_generator() -> ImageGenerator:
    """Create an ImageGenerator (requires REPLICATE_API_TOKEN env var)."""
    if not os.environ.get("REPLICATE_API_TOKEN"):
        raise ValueError("REPLICATE_API_TOKEN environment variable is required")
    return ImageGenerator()
