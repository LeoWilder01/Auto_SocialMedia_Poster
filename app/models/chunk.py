from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Chunk(Base):
    """Stores document chunks with embeddings for RAG."""
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    notion_page_id = Column(Integer, ForeignKey("notion_pages.id"), nullable=False)
    chunk_index = Column(Integer)  # Position in the document
    text = Column(Text)  # The actual chunk text
    embedding = Column(JSON)  # Vector embedding as JSON list
    keywords = Column(Text)  # Space-separated keywords for BM25
    token_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    notion_page = relationship("NotionPage", back_populates="chunks")


class NotionPageState(Base):
    """Tracks the last known state of a Notion page for change detection."""
    __tablename__ = "notion_page_states"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(String(50), unique=True, index=True)
    last_edited_time = Column(String(50))  # ISO timestamp from Notion
    content_hash = Column(String(64))  # Hash of content for change detection
    last_checked_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
