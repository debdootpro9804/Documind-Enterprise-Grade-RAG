from fastapi import APIRouter, Depends
from app.api.dependencies import supabase, get_current_user

router = APIRouter()


@router.get("/stats")
async def get_stats(user_id: str = Depends(get_current_user)):
    """Basic usage stats — extend this as needed."""
    docs = supabase.table("documents").select("id", count="exact").eq("user_id", user_id).execute()
    msgs = supabase.table("chat_messages").select("id", count="exact").eq("user_id", user_id).execute()
    return {
        "your_documents": docs.count,
        "your_messages":  msgs.count,
    }