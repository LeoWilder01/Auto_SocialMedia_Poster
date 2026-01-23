import hashlib
import re
from typing import List, Tuple
from sqlalchemy.orm import Session
from rank_bm25 import BM25Okapi
import tiktoken

from app.models.chunk import Chunk, NotionPageState
from app.models.post import NotionPage
from app.services.embeddings import get_embedding_service


class RAGService:
    """Service for RAG operations: chunking, embedding, and hybrid search."""

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = get_embedding_service()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.chunk_size = 500  # tokens
        self.chunk_overlap = 50  # tokens overlap between chunks

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    def chunk_text(self, text: str) -> List[str]:
        """Split text into chunks of approximately chunk_size tokens with overlap."""
        tokens = self.tokenizer.encode(text)
        chunks = []

        start = 0
        while start < len(tokens):
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)

            # Move start with overlap
            start = end - self.chunk_overlap
            if start >= len(tokens):
                break

        return chunks

    def extract_keywords(self, text: str) -> str:
        """Extract keywords from text for BM25 search."""
        # Remove special characters, lowercase
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text.split()

        # Filter stop words and short words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                      'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                      'could', 'should', 'may', 'might', 'can', 'this', 'that',
                      'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
                      'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}

        keywords = [w for w in words if len(w) > 2 and w not in stop_words]
        return ' '.join(keywords)

    def content_hash(self, content: str) -> str:
        """Generate hash of content for change detection."""
        return hashlib.sha256(content.encode()).hexdigest()

    def index_notion_page(self, notion_page: NotionPage, content: str) -> int:
        """Chunk and index a Notion page's content. Returns number of chunks created."""
        # Delete existing chunks for this page
        self.db.query(Chunk).filter(Chunk.notion_page_id == notion_page.id).delete()

        # Chunk the content
        chunks = self.chunk_text(content)

        # Create embeddings and store chunks
        for i, chunk_text in enumerate(chunks):
            embedding = self.embedding_service.embed_text(chunk_text)
            keywords = self.extract_keywords(chunk_text)

            chunk = Chunk(
                notion_page_id=notion_page.id,
                chunk_index=i,
                text=chunk_text,
                embedding=embedding,
                keywords=keywords,
                token_count=self.count_tokens(chunk_text)
            )
            self.db.add(chunk)

        self.db.commit()
        return len(chunks)

    def hybrid_search(self, query: str, top_k: int = 3) -> List[Tuple[Chunk, float]]:
        """
        Perform hybrid search combining vector similarity and BM25.
        Returns list of (chunk, combined_score) tuples.
        """
        # Get all chunks
        chunks = self.db.query(Chunk).all()
        if not chunks:
            return []

        # Vector search
        query_embedding = self.embedding_service.embed_text(query)
        vector_scores = []
        for chunk in chunks:
            if chunk.embedding:
                score = self.embedding_service.cosine_similarity(query_embedding, chunk.embedding)
                vector_scores.append((chunk, score))

        # BM25 search
        corpus = [chunk.keywords.split() for chunk in chunks]
        bm25 = BM25Okapi(corpus)
        query_tokens = self.extract_keywords(query).split()
        bm25_scores = bm25.get_scores(query_tokens)

        # Normalize scores
        max_vector = max([s for _, s in vector_scores]) if vector_scores else 1
        max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 1

        # Combine scores (0.7 vector + 0.3 BM25)
        combined_scores = []
        for i, chunk in enumerate(chunks):
            vector_score = next((s for c, s in vector_scores if c.id == chunk.id), 0)
            bm25_score = bm25_scores[i] if i < len(bm25_scores) else 0

            normalized_vector = vector_score / max_vector if max_vector > 0 else 0
            normalized_bm25 = bm25_score / max_bm25 if max_bm25 > 0 else 0

            combined = 0.7 * normalized_vector + 0.3 * normalized_bm25
            combined_scores.append((chunk, combined))

        # Sort by combined score and return top_k
        combined_scores.sort(key=lambda x: x[1], reverse=True)
        return combined_scores[:top_k]

    def get_context_for_query(self, query: str, top_k: int = 3) -> str:
        """Get relevant context for a query using hybrid search."""
        results = self.hybrid_search(query, top_k)
        if not results:
            return ""

        context_parts = []
        for chunk, score in results:
            context_parts.append(f"[Relevance: {score:.2f}]\n{chunk.text}")

        return "\n\n---\n\n".join(context_parts)

    def check_notion_changed(self, page_id: str, current_content: str, last_edited_time: str) -> bool:
        """Check if a Notion page has changed since last check."""
        state = self.db.query(NotionPageState).filter(
            NotionPageState.page_id == page_id
        ).first()

        current_hash = self.content_hash(current_content)

        if not state:
            # First time seeing this page
            state = NotionPageState(
                page_id=page_id,
                last_edited_time=last_edited_time,
                content_hash=current_hash
            )
            self.db.add(state)
            self.db.commit()
            return True

        # Check if content changed
        if state.content_hash != current_hash or state.last_edited_time != last_edited_time:
            state.last_edited_time = last_edited_time
            state.content_hash = current_hash
            self.db.commit()
            return True

        return False

    def update_page_state(self, page_id: str, content: str, last_edited_time: str):
        """Update the stored state for a Notion page."""
        state = self.db.query(NotionPageState).filter(
            NotionPageState.page_id == page_id
        ).first()

        current_hash = self.content_hash(content)

        if state:
            state.last_edited_time = last_edited_time
            state.content_hash = current_hash
        else:
            state = NotionPageState(
                page_id=page_id,
                last_edited_time=last_edited_time,
                content_hash=current_hash
            )
            self.db.add(state)

        self.db.commit()


def get_rag_service(db: Session) -> RAGService:
    """Create a RAG service instance."""
    return RAGService(db)
