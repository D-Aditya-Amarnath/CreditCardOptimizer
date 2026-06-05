import uuid
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext

app = FastAPI(title="Financial Offer Intelligence Agent")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

templates = Jinja2Templates(directory="backend/templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

from backend.deps import get_current_user, db
from models import UserProfile
from backend.routers import dashboard, chat, offers, user, emails, notifications, profiles, accounts, transactions, settings


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = db.get_user_by_email(email)
    if not user or not pwd_context.verify(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid email or password"},
            status_code=401
        )

    session_id = str(uuid.uuid4())
    db.create_session(session_id, user.id)

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="session_token", value=session_id, httponly=True, max_age=86400, samesite="lax")
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    return templates.TemplateResponse("auth/setup.html", {"request": request})


@app.post("/setup")
async def setup(name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    if db.get_user_by_email(email):
        raise HTTPException(400, "Email already registered")
    password_hash = pwd_context.hash(password)
    user = db.create_user(name=name, email=email, password_hash=password_hash)
    session_id = str(uuid.uuid4())
    db.create_session(session_id, user.id)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="session_token", value=session_id, httponly=True, max_age=86400, samesite="lax")
    return response


app.include_router(dashboard.router)
app.include_router(chat.router)
app.include_router(offers.router)
app.include_router(user.router)
app.include_router(emails.router)
app.include_router(notifications.router)
app.include_router(profiles.router)
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(settings.router)


@app.get("/profiles", response_class=HTMLResponse)
async def profiles_page(request: Request, user=Depends(get_current_user)):
    profiles_data = db.get_all_profiles()
    profiles = []
    for p in profiles_data:
        accounts = db.get_accounts_for_profile(p.id)
        profiles.append({
            "id": p.id,
            "name": p.name,
            "email": p.email,
            "accounts": [
                {
                    "account_email": a.account_email,
                    "account_label": a.account_label,
                    "is_primary": a.is_primary,
                    "synced_at": a.synced_at.isoformat() if a.synced_at else None
                }
                for a in accounts
            ]
        })
    return templates.TemplateResponse("profiles.html", {"request": request, "user": user, "profiles": profiles})


@app.get("/transactions", response_class=HTMLResponse)
async def transactions_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("transactions.html", {"request": request, "user": user})


@app.get("/spend-analysis", response_class=HTMLResponse)
async def spend_analysis_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("spend_analysis.html", {"request": request, "user": user})


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("settings.html", {"request": request, "user": user})


@app.get("/loading", response_class=HTMLResponse)
async def loading_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("loading.html", {"request": request, "user": user})
