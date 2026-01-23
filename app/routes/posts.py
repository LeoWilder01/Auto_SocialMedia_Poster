from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.auth import verify_api_key
from app.models.post import Post, NotionPage
from app.models.chunk import Chunk
from app.services.notion import create_reader
from app.services.llm import create_client
from app.services.mastodon import create_poster
from app.services.image import create_generator
from app.services.telegram import request_approval, notify_posted
from app.services.rag import get_rag_service

router = APIRouter(prefix="/posts", tags=["posts"])


class PostResponse(BaseModel):
    id: int
    content: str
    mastodon_url: str | None
    status: str
    created_at: datetime
    posted_at: datetime | None

    class Config:
        from_attributes = True


class NotionPageResponse(BaseModel):
    id: int
    page_id: str
    title: str
    first_processed_at: datetime
    last_processed_at: datetime

    class Config:
        from_attributes = True


class CreatePostRequest(BaseModel):
    tone: str | None = None
    use_rag: bool = True  # Enable RAG by default


class IndexResponse(BaseModel):
    page_id: str
    title: str
    chunks_created: int
    message: str


@router.get("", response_model=list[PostResponse])
async def list_posts(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key)
):
    """List all posts."""
    posts = db.query(Post).order_by(Post.created_at.desc()).all()
    return posts


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key)
):
    """Get a single post by ID."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.post("/index/{notion_page_id}", response_model=IndexResponse)
async def index_notion_page(
    notion_page_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key)
):
    """
    Index a Notion page for RAG.
    Chunks the content and creates embeddings.
    """
    reader = create_reader()
    page_info = reader.get_page_info(notion_page_id)

    # Get or create NotionPage record
    notion_page = db.query(NotionPage).filter(NotionPage.page_id == notion_page_id).first()
    if not notion_page:
        notion_page = NotionPage(page_id=notion_page_id, title=page_info["title"])
        db.add(notion_page)
        db.commit()
        db.refresh(notion_page)

    # Index the page
    rag_service = get_rag_service(db)
    chunks_created = rag_service.index_notion_page(notion_page, page_info["content"])

    # Update page state
    rag_service.update_page_state(notion_page_id, page_info["content"], page_info["last_edited_time"])

    return IndexResponse(
        page_id=notion_page_id,
        title=page_info["title"],
        chunks_created=chunks_created,
        message=f"Successfully indexed {chunks_created} chunks"
    )


@router.post("/create/{notion_page_id}", response_model=PostResponse)
async def create_post(
    notion_page_id: str,
    request: CreatePostRequest = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key)
):
    """
    Create a post from a Notion page with RAG-enhanced generation.

    This endpoint:
    1. Reads content from Notion
    2. Retrieves relevant context using hybrid search (RAG)
    3. Generates social media post with LLM + context
    4. Generates an image
    5. Sends to Telegram for approval
    6. Posts to Mastodon when approved
    7. Saves to database
    """
    tone = request.tone if request else None
    use_rag = request.use_rag if request else True

    # Read from Notion
    print(f"Reading Notion page: {notion_page_id}")
    reader = create_reader()
    page_info = reader.get_page_info(notion_page_id)
    page_title = page_info["title"]
    page_content = page_info["content"]

    # Track Notion page
    notion_page = db.query(NotionPage).filter(NotionPage.page_id == notion_page_id).first()
    if not notion_page:
        notion_page = NotionPage(page_id=notion_page_id, title=page_title)
        db.add(notion_page)
        db.commit()
        db.refresh(notion_page)
    else:
        notion_page.last_processed_at = datetime.utcnow()
        db.commit()

    # RAG: Check if page changed and re-index if needed
    rag_service = get_rag_service(db)
    if rag_service.check_notion_changed(notion_page_id, page_content, page_info["last_edited_time"]):
        print("Notion page changed, re-indexing...")
        chunks_created = rag_service.index_notion_page(notion_page, page_content)
        print(f"Indexed {chunks_created} chunks")

    # RAG: Get relevant context
    rag_context = None
    if use_rag:
        print("Retrieving RAG context...")
        rag_context = rag_service.get_context_for_query(page_content[:500], top_k=3)
        if rag_context:
            print(f"Found RAG context ({len(rag_context)} chars)")

    # Generate post with RAG context
    print("Generating social media post...")
    llm = create_client()
    post_content = llm.generate_social_post(page_content, page_title, tone, rag_context)
    print(f"Generated post ({len(post_content)} chars):\n{post_content}")

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
    print("Generating image...")
    generator = create_generator()
    image_data = generator.generate(post_content)

    # Telegram approval loop
    current_post = post_content
    while True:
        print("Sending to Telegram for approval...")
        result = await request_approval(current_post, image_data)

        if result["approved"]:
            break

        # Regenerate with new tone (still using RAG context)
        new_tone = result["tone"]
        print(f"Regenerating with {new_tone} tone...")
        current_post = llm.generate_social_post(page_content, page_title, new_tone, rag_context)
        print(f"Regenerated post:\n{current_post}")

        # Regenerate image
        image_data = generator.generate(current_post)

        # Update post in DB
        post.content = current_post
        db.commit()

    # Post to Mastodon
    print("Posting to Mastodon...")
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
    db.refresh(post)

    # Notify via Telegram
    await notify_posted(post.mastodon_url)

    print(f"Posted successfully: {post.mastodon_url}")
    return post


@router.get("/pages/", response_model=list[NotionPageResponse])
async def list_notion_pages(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key)
):
    """List all processed Notion pages."""
    pages = db.query(NotionPage).order_by(NotionPage.last_processed_at.desc()).all()
    return pages


@router.get("/chunks/", response_model=list[dict])
async def list_chunks(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key)
):
    """List all indexed chunks."""
    chunks = db.query(Chunk).order_by(Chunk.notion_page_id, Chunk.chunk_index).all()
    return [
        {
            "id": c.id,
            "notion_page_id": c.notion_page_id,
            "chunk_index": c.chunk_index,
            "text_preview": c.text[:100] + "..." if len(c.text) > 100 else c.text,
            "token_count": c.token_count,
            "has_embedding": c.embedding is not None
        }
        for c in chunks
    ]
