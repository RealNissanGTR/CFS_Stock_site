import hashlib
import hmac
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook

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
    move_inventory_item,
    get_user_by_id,
    update_user,
    delete_user,
)

from backup.backup_db import quick_backup

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "FrontEnd"

app = FastAPI(title="CFS Stock")
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
templates = Jinja2Templates(directory=str(FRONTEND_DIR))

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


def require_login(request: Request):
    user = get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return user


def require_admin(request: Request):
    user = require_login(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/home"},
        )
    return user


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


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


@app.get("/overview", response_class=HTMLResponse)
def overview(request: Request):
    user = require_login(request)
    with SessionLocal() as db:
        stocks = db.query(Stock).order_by(
            Stock.category,
            Stock.product_name,
            Stock.item_code,
            Stock.location,
        ).all()

    grouped = {}
    for stock in stocks:
        key = (stock.item_code, stock.product_name, stock.category or "Unassigned")
        if key not in grouped:
            grouped[key] = {
                "category": stock.category or "Unassigned",
                "item_code": stock.item_code,
                "product_name": stock.product_name,
                "workshop": 0,
                "paddock": 0,
                "other": [],
                "total": 0,
            }

        count = stock.stock_count or 0
        location_key = stock.location.strip().lower()
        if location_key == "workshop":
            grouped[key]["workshop"] += count
        elif location_key == "paddock":
            grouped[key]["paddock"] += count
        else:
            grouped[key]["other"].append(f"{stock.location}: {count}")

        grouped[key]["total"] += count

    return templates.TemplateResponse(
        "overview.html",
        {
            "request": request,
            "user": user,
            "products": list(grouped.values()),
        },
    )


@app.get("/home", response_class=HTMLResponse)
def home(request: Request):
    user = require_login(request)

    with SessionLocal() as db:
        stocks = db.query(Stock).order_by(
            Stock.category,
            Stock.product_name,
            Stock.item_code,
            Stock.location,
        ).all()

        categories = sorted({s.category or "Unassigned" for s in stocks})

        products_map = {}
        for s in stocks:
            key = s.item_code
            if key not in products_map:
                products_map[key] = {
                    "item_code": s.item_code,
                    "product_name": s.product_name,
                    "category": s.category or "Unassigned",
                    "workshop": 0,
                    "paddock": 0,
                    "total": 0,
                }
            count = s.stock_count or 0
            loc = (s.location or "").strip().lower()
            if loc == "workshop":
                products_map[key]["workshop"] += count
            elif loc == "paddock":
                products_map[key]["paddock"] += count
            products_map[key]["total"] += count

    return templates.TemplateResponse("home.html", {
        "request": request,
        "user": user,
        "categories": categories,
        "products": list(products_map.values()),
        "selected_item_code": request.query_params.get("item_code", ""),
        "message": request.query_params.get("message", ""),
    })

@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    try:
        user = require_admin(request)
    except Exception:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    try:
        with SessionLocal() as db:
            stocks_raw = db.query(Stock).order_by(
                Stock.category,
                Stock.product_name,
                Stock.item_code,
                Stock.location,
            ).all()

            # Build dicts INSIDE the with block while session is still open
            stocks_dict = [
                {
                    "id": s.id,
                    "item_code": s.item_code or "",
                    "product_name": s.product_name or "",
                    "category": s.category or "",
                    "stock_count": s.stock_count or 0,
                    "location": s.location or "",
                }
                for s in stocks_raw
            ]

            users = db.query(User).order_by(User.username).all()
            users_list = [
                {
                    "id": u.id,
                    "username": u.username,
                    "is_admin": u.is_admin,
                }
                for u in users
            ]

            logs_raw = db.query(Logs).order_by(Logs.timestamp.desc()).limit(200).all()
            logs_list = [
                {
                    "timestamp": l.timestamp,
                    "action": l.action,
                    "stock_name": l.stock_name,
                    "category": l.category or "",
                    "quantity": l.quantity,
                    "location": l.location,
                    "performed_by": l.performed_by or "",
                    "work_order": l.work_order or "",
                    "purchase_order": l.purchase_order or "",
                    "comments": l.comments or "",
                }
                for l in logs_raw
            ]

        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "user": user,
                "stocks": stocks_dict,
                "users": users_list,
                "logs": logs_list,
                "message": request.query_params.get("message", ""),
            },
        )

    except Exception as e:
        print(f"Admin panel error: {e}")
        return RedirectResponse(
            url=f"/home?message=Admin panel error: {str(e)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


def _normalize_item_fields(
    item_code: Optional[str],
    product_name: Optional[str],
    stock_name: Optional[str] = None,
):
    normalized_item_code = (item_code or stock_name or "").strip()
    normalized_product_name = (product_name or stock_name or "").strip()
    return normalized_item_code, normalized_product_name


def _normalize_item_code(item_code: Optional[str], stock_name: Optional[str] = None):
    return (item_code or stock_name or "").strip()


@app.post("/admin/create_stock")
def admin_create_stock(
    request: Request,
    item_code: Optional[str] = Form(None),
    product_name: Optional[str] = Form(None),
    stock_name: Optional[str] = Form(None),
    quantity: int = Form(...),
    location: str = Form("Workshop"),
    category: str = Form(""),
    comments: str = Form(""),
):
    require_admin(request)
    item_code, product_name = _normalize_item_fields(item_code, product_name, stock_name)

    if not item_code or not product_name:
        return RedirectResponse(url="/admin?message=Item code and product name are required.", status_code=status.HTTP_303_SEE_OTHER)

    create_stock_item(
        item_code=item_code,
        product_name=product_name,
        quantity=quantity,
        location=location.strip(),
        category=category.strip() or None,
        performed_by="admin",
        created_by_admin=True,
        comments=comments.strip() or None,
    )
    return RedirectResponse(url="/admin?message=Stock item created.", status_code=status.HTTP_303_SEE_OTHER)

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
        url=f"/admin?message={'User updated successfully.' if success else 'Unable to update user.'}",
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
    try:
        admin = require_admin(request)

        success = delete_user(user_id=user_id, protect_username=admin.username)
        message = "User deleted successfully." if success else "Unable to delete user (may be the last admin)."

        return RedirectResponse(url=f"/admin?message={message}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        message = f"Error deleting user: {str(e)}"
        return RedirectResponse(
            url=f"/admin?message={message}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@app.post("/inventory/change")
def inventory_change(
    request: Request,
    item_code: str = Form(...),
    location: str = Form(...),
    quantity: int = Form(...),
    direction: str = Form(...),
    order_code: str = Form(...),
    comments: str = Form(""),
    category: str = Form(""),
):
    try:
        user = require_login(request)
        item_code = item_code.strip()
        location = location.strip()

        if not item_code or quantity <= 0 or not order_code.strip():
            message = "Invalid input. Please fill all required fields."
            return RedirectResponse(
                url=f"/home?message={message}",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        if direction == "add":
            success = add_inventory_item(
                item_code=item_code,
                quantity=quantity,
                location=location,
                category=category.strip() or None,
                performed_by=user.username,
                work_order=order_code.strip(),
                comments=comments.strip() or None,
                user_is_admin=user.is_admin,
            )
            message = "Inventory added successfully." if success else "Unable to add inventory."
        else:
            success = remove_inventory_item(
                item_code=item_code,
                quantity=quantity,
                location=location,
                category=category.strip() or None,
                performed_by=user.username,
                purchase_order=order_code.strip(),
                comments=comments.strip() or None,
            )
            message = "Inventory removed successfully." if success else "Unable to remove inventory."

        quick_backup()
        return RedirectResponse(url=f"/home?message={message}", status_code=status.HTTP_303_SEE_OTHER)

    except Exception as e:
        message = f"Error: {str(e)}"
        return RedirectResponse(
            url=f"/home?message={message}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@app.post("/admin/edit_stock")
def admin_edit_stock(
    request: Request,
    stock_id: int = Form(...),
    new_item_code: str = Form(""),
    new_product_name: str = Form(""),
    new_category: str = Form(""),
    new_quantity: int = Form(None),
):
    try:
        user = require_login(request)
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin only")

        with SessionLocal() as db:
            stock = db.query(Stock).filter(Stock.id == stock_id).first()
            if not stock:
                message = "Stock item not found."
            else:
                old_name = stock.product_name
                if new_item_code.strip():
                    stock.item_code = new_item_code.strip()
                if new_product_name.strip():
                    stock.product_name = new_product_name.strip()
                if new_category.strip():
                    stock.category = new_category.strip()
                if new_quantity is not None and new_quantity >= 0:
                    stock.stock_count = new_quantity

                db.commit()
                quick_backup()
                message = f"Stock item '{old_name}' updated successfully."

        return RedirectResponse(
            url=f"/admin?message={message}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as e:
        message = f"Error updating stock: {str(e)}"
        return RedirectResponse(
            url=f"/admin?message={message}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@app.post("/inventory/delete")
def inventory_delete(
    request: Request,
    item_code: str = Form(...),
    location: str = Form(...),
):
    try:
        user = require_login(request)
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin only")

        item_code = item_code.strip()
        location = location.strip()

        if not item_code or not location:
            message = "Item code and location are required."
            return RedirectResponse(
                url=f"/admin?message={message}",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        with SessionLocal() as db:
            stock = db.query(Stock).filter(
                Stock.item_code == item_code,
                Stock.location == location,
            ).first()

            if not stock:
                message = "Stock item not found."
            else:
                product_name = stock.product_name
                db.delete(stock)
                db.commit()
                quick_backup()
                message = f"Stock item '{product_name}' deleted successfully."

        return RedirectResponse(
            url=f"/admin?message={message}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except Exception as e:
        message = f"Error deleting stock: {str(e)}"
        return RedirectResponse(
            url=f"/admin?message={message}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@app.post("/inventory/move")
def inventory_move(
    request: Request,
    item_code: str = Form(...),
    from_location: str = Form(...),
    to_location: str = Form(...),
    quantity: int = Form(...),
    comments: str = Form(""),
    category: str = Form(""),
):
    try:
        user = require_login(request)
        success = move_inventory_item(
            item_code=item_code.strip(),
            quantity=quantity,
            from_location=from_location.strip(),
            to_location=to_location.strip(),
            performed_by=user.username,
            comments=comments.strip() or None,
        )
        quick_backup()
        message = "Stock moved successfully." if success else "Unable to move stock. Check quantity and locations."
        return RedirectResponse(url=f"/home?message={message}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        return RedirectResponse(url=f"/home?message=Error moving stock: {str(e)}", status_code=status.HTTP_303_SEE_OTHER)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 303:
        response = RedirectResponse(url=exc.headers.get("location", "/home"), status_code=exc.status_code)
        return response
    
    message = "An error occurred. Please try again."
    return RedirectResponse(
        url=f"/home?message={message}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    message = "An unexpected error occurred. Please try again."
    return RedirectResponse(
        url=f"/home?message={message}",
        status_code=status.HTTP_303_SEE_OTHER,
    )