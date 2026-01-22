from fastapi import FastAPI

from app.database import init_db
from app.routes import posts

app = FastAPI(
    title="Social Media Poster API",
    description="API for creating social media posts from Notion content",
    version="1.0.0"
)

# Initialize database on startup
@app.on_event("startup")
def startup():
    init_db()

# Health check endpoint (no auth required)
@app.get("/")
async def health_check():
    return {"status": "ok", "message": "Social Media Poster API is running"}

# Include routers
app.include_router(posts.router)
