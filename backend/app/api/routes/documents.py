import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from loguru import logger
from app.api.dependencies import supabase, get_current_user
from app.services.ingestion_service import ingestion_service
from app.services.cache_service import cache_service

router = APIRouter()

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024   # 20 MB
ALLOWED_EXTENSIONS  = {".pdf", ".docx", ".txt"}


@router.post("/upload")
async def upload_document(
    file:    UploadFile = File(...),
    user_id: str        = Depends(get_current_user),
):
    """
    Upload and ingest a document.
    1. Validate file type and size
    2. Run the ingestion pipeline (parse → chunk → embed → Pinecone)
    3. Save a record in Supabase documents table
    4. Invalidate this user's answer cache (their docs changed)
    """
    # Validate extension
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"File type '{ext}' not supported. Please upload PDF, DOCX, or TXT."
        )

    # Read and validate size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(413, "File too large. Maximum size is 20 MB.")
    if len(file_bytes) == 0:
        raise HTTPException(400, "File is empty.")

    document_id = str(uuid.uuid4())

    try:
        # Run the ingestion pipeline
        result = await ingestion_service.ingest_document(
            file_bytes  = file_bytes,
            filename    = filename,
            user_id     = user_id,
            document_id = document_id,
        )

        # Save record to Supabase so the UI can list the user's documents
        supabase.table("documents").insert({
            "id":          document_id,
            "user_id":     user_id,
            "filename":    filename,
            "file_size":   len(file_bytes),
            "chunk_count": result["chunks"],
            "status":      "ready",
        }).execute()

        # Invalidate cached answers — user's knowledge base just changed
        cache_service.invalidate_user_cache(user_id)

        logger.info(f"Document uploaded | doc={document_id} | user={user_id}")
        return {
            "document_id": document_id,
            "filename":    filename,
            "chunks":      result["chunks"],
            "status":      "ready",
        }

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception(f"Ingestion failed for user={user_id}: {e}")
        raise HTTPException(500, "Document processing failed. Please try again.")


@router.get("/")
async def list_documents(user_id: str = Depends(get_current_user)):
    """Return all documents belonging to the current user."""
    result = (
        supabase.table("documents")
        .select("id, filename, file_size, chunk_count, status, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    user_id:     str = Depends(get_current_user),
):
    """
    Delete a document and all its vectors from Pinecone.
    Verifies ownership before deletion so users can't delete each other's docs.
    """
    # Verify this document belongs to the requesting user
    existing = (
        supabase.table("documents")
        .select("id")
        .eq("id", document_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(404, "Document not found.")

    # Delete vectors from Pinecone
    await ingestion_service.delete_document(document_id, user_id)

    # Delete record from Supabase
    supabase.table("documents").delete().eq("id", document_id).execute()

    # Invalidate cache again
    cache_service.invalidate_user_cache(user_id)

    logger.info(f"Document deleted | doc={document_id} | user={user_id}")
    return {"message": "Document deleted successfully."}