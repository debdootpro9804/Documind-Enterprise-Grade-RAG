from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.routes import auth, documents, chat, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging("DEBUG" if settings.app_env == "development" else "INFO")
    logger.info(f"DocuMind starting — env={settings.app_env}")
    yield
    logger.info("DocuMind shutting down")


app = FastAPI(
    title       = "DocuMind API",
    description = "Enterprise RAG platform",
    version     = "1.0.0",
    lifespan    = lifespan,
    docs_url    = "/api/docs",
    redoc_url   = "/api/redoc",
)

# CORS — must be added BEFORE any routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )

# Routes
app.include_router(auth.router,      prefix="/api/auth",      tags=["Auth"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(chat.router,      prefix="/api/chat",      tags=["Chat"])
app.include_router(admin.router,     prefix="/api/admin",     tags=["Admin"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": settings.app_name}

@app.get("/health")
async def health_root():
    return {"status": "ok", "service": settings.app_name}

@app.get("/")
async def root():
    return {"status": "ok", "service": settings.app_name}