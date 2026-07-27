import os
import hashlib
import binascii
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Boolean, create_engine, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    email = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)

class Stock(Base):
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=True, index=True)
    item_code = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=False, index=True)
    stock_count = Column(Integer, nullable=False, default=0)
    location = Column(String, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("item_code", "location", name="uix_item_code_location"),
    )

class Logs(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False)
    stock_name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    quantity = Column(Integer, nullable=False)
    location = Column(String, nullable=False)
    performed_by = Column(String, nullable=True)
    work_order = Column(String, nullable=True)
    purchase_order = Column(String, nullable=True)
    comments = Column(String, nullable=True)
    timestamp = Column(String, nullable=False, default=lambda: datetime.utcnow().isoformat())

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./stock.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return binascii.hexlify(salt + dk).decode("ascii")

def verify_password(password: str, password_hash: str) -> bool:
    try:
        data = binascii.unhexlify(password_hash.encode("ascii"))
        salt = data[:16]
        stored_dk = data[16:]
        new_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return secrets.compare_digest(new_dk, stored_dk)
    except Exception:
        return False

def init_db(default_admin_username: str = "admin", default_admin_password: str = "admin"):
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        existing = session.query(User).filter_by(username=default_admin_username).first()
        if not existing:
            admin_user = User(
                username=default_admin_username,
                password_hash=hash_password(default_admin_password),
                is_admin=True,
            )
            session.add(admin_user)
            session.commit()

def _log_inventory_action(
    session: Session,
    action: str,
    stock_name: str,
    category: Optional[str],
    quantity: int,
    location: str,
    performed_by: Optional[str] = None,
    work_order: Optional[str] = None,
    purchase_order: Optional[str] = None,
    comments: Optional[str] = None,
):
    log = Logs(
        action=action,
        stock_name=stock_name,
        category=category,
        quantity=quantity,
        location=location,
        performed_by=performed_by,
        work_order=work_order,
        purchase_order=purchase_order,
        comments=comments,
        timestamp=datetime.utcnow().isoformat(),
    )
    session.add(log)

def create_stock_item(
    item_code: str,
    product_name: str,
    quantity: int,
    location: str = "Workshop",
    category: Optional[str] = None,
    performed_by: Optional[str] = None,
    created_by_admin: bool = False,
    comments: Optional[str] = None,
) -> bool:
    if not created_by_admin or quantity < 0 or not item_code or not product_name:
        return False

    with SessionLocal() as db:
        existing = db.query(Stock).filter_by(item_code=item_code, location=location).first()
        if existing:
            return False

        stock = Stock(
            item_code=item_code,
            product_name=product_name,
            category=category,
            stock_count=quantity,
            location=location,
        )
        db.add(stock)
        _log_inventory_action(
            session=db,
            action="create",
            stock_name=product_name,
            category=category,
            quantity=quantity,
            location=location,
            performed_by=performed_by,
            work_order=None,
            purchase_order=None,
            comments=comments,
        )
        db.commit()
        return True

def delete_stock_item(
    item_code: str,
    location: str = "Workshop",
    performed_by: Optional[str] = None,
    deleted_by_admin: bool = False,
    comments: Optional[str] = None,
) -> bool:
    if not deleted_by_admin:
        return False

    with SessionLocal() as db:
        stock = db.query(Stock).filter_by(item_code=item_code, location=location).first()
        if stock is None:
            return False

        _log_inventory_action(
            session=db,
            action="delete",
            stock_name=stock.product_name,
            category=stock.category,
            quantity=stock.stock_count,
            location=location,
            performed_by=performed_by,
            comments=comments,
        )
        db.delete(stock)
        db.commit()
        return True

def add_inventory_item(
    item_code: str,
    quantity: int,
    location: str = "Workshop",
    category: Optional[str] = None,
    performed_by: Optional[str] = None,
    work_order: Optional[str] = None,
    comments: Optional[str] = None,
    user_is_admin: bool = False,
) -> bool:
    if quantity <= 0 or not work_order:
        return False

    with SessionLocal() as db:
        stock = db.query(Stock).filter_by(item_code=item_code, location=location).first()
        if stock is None:
            return False

        stock.stock_count += quantity
        _log_inventory_action(
            session=db,
            action="add",
            stock_name=stock.product_name,
            category=category or stock.category,
            quantity=quantity,
            location=location,
            performed_by=performed_by,
            work_order=work_order,
            comments=comments,
        )
        db.commit()
        return True

def remove_inventory_item(
    item_code: str,
    quantity: int,
    location: str = "Workshop",
    category: Optional[str] = None,
    performed_by: Optional[str] = None,
    purchase_order: Optional[str] = None,
    comments: Optional[str] = None,
) -> bool:
    if quantity <= 0 or not purchase_order:
        return False

    with SessionLocal() as db:
        stock = db.query(Stock).filter_by(item_code=item_code, location=location).first()
        if stock is None or stock.stock_count < quantity:
            return False

        stock.stock_count -= quantity
        _log_inventory_action(
            session=db,
            action="remove",
            stock_name=stock.product_name,
            category=category or stock.category,
            quantity=quantity,
            location=location,
            performed_by=performed_by,
            purchase_order=purchase_order,
            comments=comments,
        )
        db.commit()
        return True

def add_user_full(username: str, password: str, email: Optional[str] = None, is_admin: bool = False) -> bool:
    init_db()
    with SessionLocal() as db:
        if db.query(User).filter_by(username=username).first():
            return False
        user = User(
            username=username,
            password_hash=hash_password(password),
            email=email,
            is_admin=is_admin,
        )
        db.add(user)
        db.commit()
        return True

def get_user(username: str) -> Optional[User]:
    with SessionLocal() as db:
        return db.query(User).filter_by(username=username).first()

def get_user_by_id(user_id: int) -> Optional[User]:
    with SessionLocal() as db:
        return db.query(User).filter_by(id=user_id).first()

def update_user(
    user_id: int,
    new_username: Optional[str] = None,
    new_password: Optional[str] = None,
    is_admin: Optional[bool] = None,
) -> bool:
    if new_username is None and new_password is None and is_admin is None:
        return False

    with SessionLocal() as db:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return False

        if new_username:
            duplicate = db.query(User).filter(User.username == new_username, User.id != user_id).first()
            if duplicate:
                return False
            user.username = new_username

        if new_password:
            user.password_hash = hash_password(new_password)

        if is_admin is not None:
            user.is_admin = is_admin

        db.commit()
        return True

def delete_user(user_id: int, protect_username: Optional[str] = None) -> bool:
    with SessionLocal() as db:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return False

        if protect_username and user.username == protect_username:
            return False

        if user.is_admin:
            admin_count = db.query(User).filter_by(is_admin=True).count()
            if admin_count <= 1:
                return False

        db.delete(user)
        db.commit()
        return True
