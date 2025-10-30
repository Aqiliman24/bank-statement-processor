"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from utils.config import settings
from routes.routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.debug else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Bank Statement Processor API")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    
    # Create upload directory
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(exist_ok=True)
    logger.info(f"Upload directory: {upload_dir.absolute()}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Bank Statement Processor API")


# Create FastAPI app
app = FastAPI(
    title="Bank Statement Processor",
    description="Extract financial data from bank statement PDFs using OCR and LLM",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["bank_statements"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Bank Statement Processor API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
