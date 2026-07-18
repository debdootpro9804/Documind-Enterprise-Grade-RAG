import uuid
import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger
from app.api.dependencies import supabase, get_current_user
from app.services.rag_service import rag_service
from app.services.cache_service import cache_service

router = APIRouter()


class ChatRequest(BaseModel):
    question:     str
    session_id:   str | None = None
    document_ids: list[str] | None = None  # None means search all user docs


@router.post("/stream")
async def chat_stream(
    body:    ChatRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Main chat endpoint. Returns a streaming SSE response.

    SSE (Server-Sent Events) is a protocol where the server keeps the HTTP
    connection open and pushes data as it becomes available. The frontend
    reads each chunk and appends it to the message in real time.

    Each SSE event looks like:
        data: {"token": "Hello"}\n\n
        data: {"token": " world"}\n\n
        data: [DONE]\n\n
    """
    if not body.question.strip():
        raise HTTPException(400, "Question cannot be empty.")

    # Step 1 — rate limit check
    allowed, remaining = cache_service.check_rate_limit(user_id)
    if not allowed:
        raise HTTPException(
            429,
            "You've sent too many requests. Please wait a moment before trying again."
        )

    # Step 2 — check cache for identical question
    cached_answer = cache_service.get_cached_answer(user_id, body.question)
    if cached_answer:
        # Return the cached answer as a single SSE event so the
        # frontend handles it identically to a streamed response
        async def cached_stream():
            yield f"data: {json.dumps({'token': cached_answer, 'cached': True})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            cached_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control":     "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Step 3 — load chat history for this session (enables follow-up questions)
    chat_history = []
    session_id   = body.session_id or str(uuid.uuid4())

    if body.session_id:
        history_result = (
            supabase.table("chat_messages")
            .select("role, content")
            .eq("session_id", body.session_id)
            .order("created_at")
            .limit(12)
            .execute()
        )
        chat_history = history_result.data or []

    # Step 4 — stream the RAG response
    async def stream_generator():
        full_response_tokens = []

        try:
            async for token in rag_service.query_stream(
                question     = body.question,
                user_id      = user_id,
                chat_history = chat_history,
                document_ids = body.document_ids,
            ):
                full_response_tokens.append(token)
                # Each token is sent as a JSON-encoded SSE event
                yield f"data: {json.dumps({'token': token})}\n\n"

            # Signal to the frontend that streaming is complete
            yield "data: [DONE]\n\n"

            # After streaming completes, persist everything
            full_answer = "".join(full_response_tokens)

            # Save to answer cache
            cache_service.set_cached_answer(user_id, body.question, full_answer)

            # If this is a new session, create the session row first.
            # chat_messages has a foreign key on session_id so the
            # session must exist before we can insert messages.
            if not body.session_id:
                supabase.table("chat_sessions").insert({
                    "id":      session_id,
                    "user_id": user_id,
                    "title":   body.question[:60],
                }).execute()

            # Now safe to insert messages
            supabase.table("chat_messages").insert([
                {
                    "session_id": session_id,
                    "user_id":    user_id,
                    "role":       "user",
                    "content":    body.question,
                },
                {
                    "session_id": session_id,
                    "user_id":    user_id,
                    "role":       "assistant",
                    "content":    full_answer,
                },
            ]).execute()

            logger.info(
                f"Chat complete | user={user_id} | session={session_id} | "
                f"tokens={len(full_response_tokens)}"
            )

        except Exception as e:
            logger.exception(f"Stream error for user={user_id}: {e}")
            yield f"data: {json.dumps({'error': 'Something went wrong. Please try again.'})}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":          "no-cache",
            "X-Accel-Buffering":      "no",
            "X-RateLimit-Remaining":  str(remaining),
        },
    )


@router.get("/sessions")
async def get_sessions(user_id: str = Depends(get_current_user)):
    """Return all chat sessions for the current user."""
    result = (
        supabase.table("chat_sessions")
        .select("id, title, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    user_id:    str = Depends(get_current_user),
):
    """Return all messages in a specific chat session."""
    result = (
        supabase.table("chat_messages")
        .select("role, content, created_at")
        .eq("session_id", session_id)
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return result.data