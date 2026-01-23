from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.database import init_db
from app.routes import posts
from app.services.scheduler import get_poller, on_notion_change


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app."""
    # Startup
    init_db()
    print("Database initialized")

    # Start Notion poller
    poller = get_poller()
    poller.on_change_callback = on_notion_change
    await poller.start()

    yield

    # Shutdown
    await poller.stop()


app = FastAPI(
    title="Social Media Poster API",
    description="API for creating social media posts from Notion content with RAG",
    version="2.0.0",
    lifespan=lifespan
)


# Health check endpoint (no auth required)
@app.get("/")
async def health_check():
    return {
        "status": "ok",
        "message": "Social Media Poster API is running",
        "features": ["RAG", "Hybrid Search", "Notion Polling"]
    }


# Include routers
app.include_router(posts.router)
