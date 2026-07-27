import hashlib
import hmac
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
    get_user_by_id,
    update_user,
    delete_user,
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
TEMPLATE_DIR = PROJECT_ROOT / "FrontEnd"
STATIC_DIR = PROJECT_ROOT / "FrontEnd"

app = FastAPI(title="CFS Stock")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret")
COOKIE_NAME = "cfs_auth"
COOKIE_MAX_AGE = 3600

init_db()


def _sign_payload(payload: str) -> str:
    return hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _make_cookie_value(user: User) -> str:
    payload = f"{user.username}:{int(user.is_admin)}"
    return f"{payload}:{_sign_payload(payload)}"


def _parse_cookie_value(cookie_value: Optional[str]) -> Optional[tuple[str, bool]]:
    if not cookie_value:
        return None

    parts = cookie_value.rsplit(":", 1)
    if len(parts) != 2:
        return None

    payload, signature = parts
    if not hmac.compare_digest(signature, _sign_payload(payload)):
        return None

    payload_parts = payload.rsplit(":", 1)
    if len(payload_parts) != 2:
        return None

    username, is_admin_text = payload_parts
    return username, bool(int(is_admin_text))


def get_current_user(request: Request) -> Optional[User]:
    cookie_value = request.cookies.get(COOKIE_NAME)
    parsed = _parse_cookie_value(cookie_value)
    if not parsed:
        return None

    username, _ = parsed
    with SessionLocal() as db:
        return db.query(User).filter_by(username=username).first()


def require_login(request: Request) -> User:
    user = get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return user


def require_admin(request: Request) -> User:
    user = require_login(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/home"},
        )
    return user


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with SessionLocal() as db:
        user = db.query(User).filter_by(username=username.strip()).first()
        if user and verify_password(password.strip(), user.password_hash):
            response = RedirectResponse(url="/home", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(
                key=COOKIE_NAME,
                value=_make_cookie_value(user),
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


@app.get("/home", response_class=HTMLResponse)
def home(request: Request):
    user = require_login(request)
    with SessionLocal() as db:
        stocks = db.query(Stock).order_by(Stock.category, Stock.stock_name, Stock.location).all()

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "user": user,
            "stocks": stocks,
            "message": request.query_params.get("message", ""),
        },
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    user = require_admin(request)
    with SessionLocal() as db:
        stocks = db.query(Stock).order_by(Stock.category, Stock.stock_name, Stock.location).all()
        users = db.query(User).order_by(User.username).all()
        logs = db.query(Logs).order_by(Logs.timestamp.desc()).limit(200).all()

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "stocks": stocks,
            "users": users,
            "logs": logs,
            "message": request.query_params.get("message", ""),
        },
    )


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
    user = require_login(request)
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
    user = require_login(request)
    success = remove_inventory_item(
        stock_name=stock_name.strip(),
        quantity=quantity,
        location=location.strip(),
        category=category.strip() or None,
        performed_by=user.username,
        purchase_order=purchase_order.strip(),
        comments=comments.strip() or None,
    )

    redirect_path = "/dashboard" if user.is_admin else "/home"
    message = "Inventory removed successfully." if success else "Unable to remove inventory."
    return RedirectResponse(url=f"{redirect_path}?message={message}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/add_user")
def admin_add_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    is_admin: str = Form(""),
):
    require_admin(request)
    add_user_full(
        username=username.strip(),
        password=password.strip(),
        is_admin=bool(is_admin),
    )
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/toggle_admin/{user_id}")
def admin_toggle_admin(request: Request, user_id: int):
    require_admin(request)
    with SessionLocal() as db:
        target = db.query(User).filter_by(id=user_id).first()
        if target:
            target.is_admin = not target.is_admin
            db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/create_stock")
def admin_create_stock(
    request: Request,
    stock_name: str = Form(...),
    quantity: int = Form(...),
    location: str = Form("Workshop"),
    category: str = Form(""),
    comments: str = Form(""),
):
    require_admin(request)
    create_stock_item(
        stock_name=stock_name.strip(),
        quantity=quantity,
        location=location.strip(),
        category=category.strip() or None,
        performed_by="admin",
        created_by_admin=True,
        comments=comments.strip() or None,
    )
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/delete_stock")
def admin_delete_stock(
    request: Request,
    stock_name: str = Form(...),
    location: str = Form("Workshop"),
    comments: str = Form(""),
):
    require_admin(request)
    delete_stock_item(
        stock_name=stock_name.strip(),
        location=location.strip(),
        performed_by="admin",
        deleted_by_admin=True,
        comments=comments.strip() or None,
    )
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/edit_user")
def admin_edit_user(
    request: Request,
    user_id: int = Form(...),
    new_username: str = Form(""),
    new_password: str = Form(""),
    is_admin: str = Form(None),
):
    admin = require_admin(request)

    success = update_user(
        user_id=user_id,
        new_username=new_username.strip() or None,
        new_password=new_password.strip() or None,
        is_admin=bool(is_admin),
    )

    response = RedirectResponse(
        url=f"/dashboard?message={'User updated successfully.' if success else 'Unable to update user.'}",
        status_code=status.HTTP_303_SEE_OTHER,
    )

    if success and user_id == admin.id:
        updated = get_user_by_id(user_id)
        if updated:
            response.set_cookie(
                key=COOKIE_NAME,
                value=_make_cookie_value(updated),
                httponly=True,
                max_age=COOKIE_MAX_AGE,
                expires=COOKIE_MAX_AGE,
                samesite="lax",
            )

    return response


@app.post("/admin/delete_user/{user_id}")
def admin_delete_user(request: Request, user_id: int):
    admin = require_admin(request)

    formatted = delete_user(user_id=user_id, protect_username=admin.username)
    message = "User deleted successfully." if formatted else "Unable to delete user."

    return RedirectResponse(url=f"/dashboard?message={message}", status_code=status.HTTP_303_SEE_OTHER)
