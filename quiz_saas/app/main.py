from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from .routers import dashboard, auth
import os

app = FastAPI(title="Quiz Solver SaaS")

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & Templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Routers
app.include_router(auth.router)
app.include_router(dashboard.router)

# Root route
@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.on_event("startup")
async def startup_event():
    # 1. Create Tables
    from .database import engine, Base
    from .models import User, GameAccount
    from .database import SessionLocal
    from .services.browser_manager import BrowserManager
    
    Base.metadata.create_all(bind=engine)
    
    # 2. Create Demo User/Account
    db = SessionLocal()
    if not db.query(User).filter(User.username == "demo").first():
        demo_user = User(username="demo", password_hash="demo", balance=100000)
        db.add(demo_user)
        db.commit()
        
        acc1 = GameAccount(
            user_id=demo_user.id,
            name="Account 1 (Auto)",
            username="demo_onluyen",
            password="password",
            status="Offline"
        )
        db.add(acc1)
        db.commit()
        print("created demo account")
        
    # 3. Auto-launch Browser for acc1 (Demo ID: 1 or 'acc1' mapping)
    # Mapping ID 1 -> 'acc1' for simplicity with current strings
    # print("Launching Demo Browser 'acc1'...")
    # BrowserManager.create_session("acc1")  # Commented: Opens Chrome on backend startup
    db.close()

if __name__ == "__main__":
    import uvicorn
    # Use the import string format for reload to work properly
    uvicorn.run("quiz_saas.app.main:app", host="0.0.0.0", port=8000, reload=True)
