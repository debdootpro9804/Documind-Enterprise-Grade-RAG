from fastapi import HTTPException, Header
from supabase import create_client
from app.core.config import settings

# One shared Supabase client for all routes
supabase = create_client(settings.supabase_url, settings.supabase_service_key)


async def get_current_user(authorization: str = Header(...)) -> str:
    """
    Validates the Supabase JWT from the Authorization header.
    Returns the user's ID string if valid.
    Raises HTTP 401 if the token is missing, expired, or invalid.

    Every protected route depends on this function.
    FastAPI calls it automatically when you declare it as a dependency.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header must start with 'Bearer '"
        )

    token = authorization.removeprefix("Bearer ").strip()

    try:
        response = supabase.auth.get_user(token)
        return response.user.id
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token. Please log in again."
        )