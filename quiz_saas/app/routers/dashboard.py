from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
import os
# Use relative imports, works when run as module
from ..services.browser_manager import BrowserManager
from ..services.proxy_service import ProxyService

# Setup templates here too or import from main? 
# Better to direct import templates logic or re-init
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

router = APIRouter()

@router.get("/dashboard")
def dashboard_view(request: Request):
    # Mock data
    accounts = [
        {"id": "acc1", "name": "Account 1", "status": "Ready"},
        {"id": "acc2", "name": "Account 2", "status": "Running"}
    ]
    return templates.TemplateResponse("dashboard.html", {"request": request, "accounts": accounts})

@router.get("/session/{account_id}")
def session_allow(request: Request, account_id: str):
    return templates.TemplateResponse("session.html", {"request": request, "account_id": account_id})

@router.get("/stream/{account_id}")
def stream_video(account_id: str):
    session = BrowserManager.get_session(account_id)
    if not session:
        return Response("Session not found", status_code=404)
        
    return StreamingResponse(
        session.stream_frame(), 
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.post("/control/{account_id}")
async def control_input(account_id: str, request: Request):
    data = await request.json()
    session = BrowserManager.get_session(account_id)
    if session:
        session.handle_input(data.get('type'), data)
        return {"status": "ok"}
    return {"status": "error"}

@router.post("/start_solver/{account_id}")
def start_solver(account_id: str):
    session = BrowserManager.get_session(account_id)
    if session:
        session.start_solving_task()
        return {"status": "started"}
    return {"status": "error"}

@router.post("/stop_solver/{account_id}")
def stop_solver(account_id: str):
    session = BrowserManager.get_session(account_id)
    if session:
        session.stop_solving_task()
        return {"status": "stopped"}
    return {"status": "error"}

@router.post("/create_session/{account_id}")
def create_session(account_id: str):
    session = BrowserManager.create_session(account_id)
    if session:
        return {"status": "created"}
    return {"status": "error"}
