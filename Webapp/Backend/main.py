import os
import time
from datetime import timedelta
from typing import Optional

import jwt
from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from db.db_init import (
    SessionLocal,
    User,
    Stock,
    Logs,
    init_db,
    verify_password,
    add_user_full,
    create_stock_item,
    delete_stock_item,
    add_inventory_item,
    remove_inventory_item,
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="../FrontEnd"), name="static")
templates = Jinja2Templates(directory="../FrontEnd")

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret")
COOKIE_NAME = "cfs_auth"
COOKIE_MAX_AGE = 3600

init_db()


def create_access_token(username: str, is_admin: bool) -> str:
    payload = {
        "sub": username,
        "is_admin": is_admin,
        "exp": time.time() + COOKIE_MAX_AGE,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None


def get_current_user(request: Request) -> Optional[User]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    username = payload["sub"]
    with SessionLocal() as db:
        return db.query(User).filter_by(username=username).first()


def require_user(request: Request) -> Optional[User]:
    user = get_current_user(request)
    if user is None:
        raise RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return user


def require_admin(request: Request) -> User:
    user = get_current_user(request)
    if user is None or not user.is_admin:
        raise RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return user


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


def render_home(request: Request, message: str = ""):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    with SessionLocal() as db:
        stocks = db.query(Stock).order_by(Stock.category, Stock.stock_name, Stock.location).all()
        users = []
        logs = []
        if user.is_admin:
            users = db.query(User).order_by(User.username).all()
            logs = db.query(Logs).order_by(Logs.timestamp.desc()).limit(100).all()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "stocks": stocks,
            "users": users,
            "logs": logs,
            "message": message,
        },
    )


@app.get("/home", response_class=HTMLResponse)
def home(request: Request):
    return render_home(request)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return render_home(request)


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with SessionLocal() as db:
        user = db.query(User).filter_by(username=username.strip()).first()
        if user and verify_password(password.strip(), user.password_hash):
            token = create_access_token(user.username, bool(user.is_admin))
            response = RedirectResponse(url="/home", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(
                key=COOKIE_NAME,
                value=token,
                httponly=True,
                max_age=COOKIE_MAX_AGE,
                expires=COOKIE_MAX_AGE,
                samesite="lax",
            )
            return response

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid username or password."},
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.post("/inventory/add")
def inventory_add(
    request: Request,
    stock_name: str = Form(...),
    quantity: int = Form(...),
    location: str = Form("Workshop"),
    work_order: str = Form(...),
    comments: str = Form(""),
    category: str = Form(""),
):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    success = add_inventory_item(
        stock_name=stock_name.strip(),
        quantity=quantity,
        location=location.strip(),
        category=category.strip() or None,
        performed_by=user.username,
        work_order=work_order.strip(),
        comments=comments.strip() or None,
        user_is_admin=user.is_admin,
    )

    message = "Inventory added successfully." if success else "Unable to add inventory."
    return RedirectResponse(url=f"/dashboard?message={message}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/inventory/remove")
def inventory_remove(
    request: Request,
    stock_name: str = Form(...),
    quantity: int = Form(...),
    location: str = Form("Workshop"),
    purchase_order: str = Form(...),
    comments: str = Form(""),
    category: str = Form(""),
):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    success = remove_inventory_item(
        stock_name=stock_name.strip(),
        quantity=quantity,
        location=location.strip(),
        category=category.strip() or None,
        performed_by=user.username,
        purchase_order=purchase_order.strip(),
        comments=comments.strip() or None,
    )

    message = "Inventory removed successfully." if success else "Unable to remove inventory."
    return RedirectResponse(url=f"/dashboard?message={message}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    user = require_admin(request)
    with SessionLocal() as db:
        users = db.query(User).order_by(User.username).all()
        logs = db.query(Logs).order_by(Logs.timestamp.desc()).limit(200).all()
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "logs": logs,
        },
    )


@app.post("/admin/add_user")
def admin_add_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    is_admin: Optional[str] = Form(None),
):
    user = require_admin(request)
    add_user_full(
        username=username.strip(),
        password=password.strip(),
        is_admin=bool(is_admin),
    )
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/toggle_admin/{user_id}")
def admin_toggle_admin(request: Request, user_id: int):
    user = require_admin(request)
    with SessionLocal() as db:
        target = db.query(User).filter_by(id=user_id).first()
        if target and target.username != user.username:
            target.is_admin = not bool(target.is_admin)
            db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/create_stock")
def admin_create_stock(
    request: Request,
    stock_name: str = Form(...),
    quantity: int = Form(...),
    location: str = Form("Workshop"),
    category: str = Form(""),
    comments: str = Form(""),
):
    user = require_admin(request)
    create_stock_item(
        stock_name=stock_name.strip(),
        quantity=quantity,
        location=location.strip(),
        category=category.strip() or None,
        performed_by=user.username,
        created_by_admin=True,
        comments=comments.strip() or None,
    )
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/delete_stock")
def admin_delete_stock(
    request: Request,
    stock_name: str = Form(...),
    location: str = Form("Workshop"),
    comments: str = Form(""),
):
    user = require_admin(request)
    delete_stock_item(
        stock_name=stock_name.strip(),
        location=location.strip(),
        performed_by=user.username,
        deleted_by_admin=True,
        comments=comments.strip() or None,
    )
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
