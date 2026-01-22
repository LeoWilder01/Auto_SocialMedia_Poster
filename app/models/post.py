from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class NotionPage(Base):
    """Tracks which Notion pages have been processed."""
    __tablename__ = "notion_pages"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(String(50), unique=True, index=True)
    title = Column(String(255))
    first_processed_at = Column(DateTime, default=datetime.utcnow)
    last_processed_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    posts = relationship("Post", back_populates="notion_page")


class Post(Base):
    """Stores post history."""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    mastodon_url = Column(String(255), nullable=True)
    mastodon_id = Column(String(50), nullable=True)
    status = Column(String(20), default="pending")  # pending, approved, posted, rejected
    notion_page_id = Column(Integer, ForeignKey("notion_pages.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    posted_at = Column(DateTime, nullable=True)

    notion_page = relationship("NotionPage", back_populates="posts")
