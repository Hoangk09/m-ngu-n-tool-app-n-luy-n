from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from .. import database, models
from ..services.browser_manager import BrowserManager # To load accounts on login maybe?

router = APIRouter()

# Password hashing (using simple string for demo, use passlib in production)
def verify_password(plain_password, hashed_password):
    return plain_password == hashed_password # TODO: Use bcrypt

def get_password_hash(password):
    return password # TODO: Use bcrypt

@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse(url="/?error=Invalid Credentials", status_code=status.HTTP_303_SEE_OTHER)
    
    # Set session cookie
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="user_id", value=str(user.id))
    return response

@router.post("/register")
async def register(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if user:
         return RedirectResponse(url="/?error=Username exists", status_code=status.HTTP_303_SEE_OTHER)
         
    new_user = models.User(username=username, password_hash=get_password_hash(password))
    db.add(new_user)
    db.commit()
    
    # Auto login
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="user_id", value=str(new_user.id))
    return response

@router.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("user_id")
    return response
