from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from agent4_gradio_rag.backend.deps import get_current_user
from shared_core.models import UserProfile, ProfileAccountMapping
from shared_core.database import db

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


class ProfileCreate(BaseModel):
    name: str
    email: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = None


class AccountAssignRequest(BaseModel):
    profile_id: int
    account_email: str
    account_label: Optional[str] = None
    is_primary: bool = False


class ProfileResponse(BaseModel):
    id: int
    name: str
    email: str
    accounts: List[dict]

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ProfileResponse])
async def list_profiles(current_user=Depends(get_current_user)):
    profiles = db.get_all_profiles()
    result = []
    for p in profiles:
        accounts = db.get_accounts_for_profile(p.id)
        result.append(ProfileResponse(
            id=p.id,
            name=p.name,
            email=p.email,
            accounts=[
                {
                    "account_email": a.account_email,
                    "account_label": a.account_label,
                    "is_primary": a.is_primary,
                    "synced_at": a.synced_at.isoformat() if a.synced_at else None
                }
                for a in accounts
            ]
        ))
    return result


@router.post("/", response_model=ProfileResponse)
async def create_profile(data: ProfileCreate, current_user=Depends(get_current_user)):
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    if db.get_user_by_email(data.email):
        raise HTTPException(400, "Email already registered")
    
    user = db.create_user(
        name=data.name,
        email=data.email,
        password_hash=pwd_context.hash("changeme123")
    )
    
    return ProfileResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        accounts=[]
    )


@router.put("/{profile_id}", response_model=ProfileResponse)
async def update_profile(profile_id: int, data: ProfileUpdate, current_user=Depends(get_current_user)):
    with db.get_session() as session:
        from sqlalchemy import func
        profile = session.query(UserProfile).filter(UserProfile.id == profile_id).first()
        if not profile:
            raise HTTPException(404, "Profile not found")
        
        if data.name:
            profile.name = data.name
        
        session.commit()
        session.refresh(profile)
        
        accounts = db.get_accounts_for_profile(profile.id)
        return ProfileResponse(
            id=profile.id,
            name=profile.name,
            email=profile.email,
            accounts=[
                {
                    "account_email": a.account_email,
                    "account_label": a.account_label,
                    "is_primary": a.is_primary,
                    "synced_at": a.synced_at.isoformat() if a.synced_at else None
                }
                for a in accounts
            ]
        )


@router.delete("/{profile_id}")
async def delete_profile(profile_id: int, current_user=Depends(get_current_user)):
    with db.get_session() as session:
        profile = session.query(UserProfile).filter(UserProfile.id == profile_id).first()
        if not profile:
            raise HTTPException(404, "Profile not found")
        
        session.query(ProfileAccountMapping).filter(
            ProfileAccountMapping.profile_id == profile_id
        ).delete()
        session.delete(profile)
        session.commit()
    
    return {"status": "ok"}


@router.post("/assign-account")
async def assign_account(data: AccountAssignRequest, current_user=Depends(get_current_user)):
    mapping = db.assign_account_to_profile(
        profile_id=data.profile_id,
        account_email=data.account_email,
        label=data.account_label,
        is_primary=data.is_primary
    )
    return {
        "status": "ok",
        "account_email": mapping.account_email,
        "profile_id": mapping.profile_id
    }


@router.delete("/accounts/{account_email}")
async def remove_account(account_email: str, current_user=Depends(get_current_user)):
    db.remove_account_mapping(account_email)
    return {"status": "ok"}
