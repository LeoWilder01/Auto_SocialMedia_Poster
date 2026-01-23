from fastembed import TextEmbedding
from typing import List
import numpy as np


class EmbeddingService:
    """Service for generating text embeddings using fastembed."""

    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is None:
            print("Loading embedding model...")
            self._model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
            print("Embedding model loaded.")

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        embeddings = list(self._model.embed([text]))
        return embeddings[0].tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = list(self._model.embed(texts))
        return [emb.tolist() for emb in embeddings]

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def get_embedding_service() -> EmbeddingService:
    """Get the singleton embedding service instance."""
    return EmbeddingService()
