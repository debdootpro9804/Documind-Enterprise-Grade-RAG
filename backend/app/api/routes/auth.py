from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from loguru import logger
from app.api.dependencies import supabase

router = APIRouter()


class SignUpRequest(BaseModel):
    email:     EmailStr
    password:  str
    full_name: str


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


@router.post("/signup")
async def signup(body: SignUpRequest):
    """
    Create a new account via Supabase Auth.
    Supabase handles password hashing, email verification, everything.
    """
    try:
        res = supabase.auth.sign_up({
            "email":    body.email,
            "password": body.password,
            "options":  {
                "data": {"full_name": body.full_name}
            },
        })
        if res.user is None:
            raise HTTPException(400, "Signup failed. Please try again.")

        logger.info(f"New user signed up: {body.email}")
        return {
            "message": "Account created. Please check your email to verify your account.",
            "user_id": res.user.id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(400, str(e))


@router.post("/login")
async def login(body: LoginRequest):
    """
    Sign in with email + password.
    Returns access_token (JWT) and refresh_token.
    The frontend stores the access_token and sends it with every request.
    """
    try:
        res = supabase.auth.sign_in_with_password({
            "email":    body.email,
            "password": body.password,
        })
        logger.info(f"User logged in: {body.email}")
        return {
            "access_token":  res.session.access_token,
            "refresh_token": res.session.refresh_token,
            "user": {
                "id":        res.user.id,
                "email":     res.user.email,
                "full_name": res.user.user_metadata.get("full_name", ""),
            },
        }
    except Exception as e:
        logger.error(f"Login failed for {body.email}: {e}")
        raise HTTPException(401, "Invalid email or password.")


@router.post("/logout")
async def logout():
    supabase.auth.sign_out()
    return {"message": "Logged out successfully."}