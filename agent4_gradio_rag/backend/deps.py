from fastapi import Header, HTTPException
from typing import Optional
from shared_core.database import DatabaseManager
from shared_core.models import UserProfile

db = DatabaseManager()
db.initialize_schema()


def get_current_user(session_token: Optional[str] = Header(None)) -> UserProfile:
    if not session_token:
        raise HTTPException(401, "Not authenticated. Please login.")

    user = db.get_user_by_session(session_token)
    if not user:
        raise HTTPException(401, "Invalid or expired session. Please login again.")

    return user


def get_optional_user(session_token: Optional[str] = Header(None)) -> Optional[UserProfile]:
    if not session_token:
        return None
    return db.get_user_by_session(session_token)
