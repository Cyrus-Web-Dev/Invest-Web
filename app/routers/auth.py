from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ratelimit import add_hit, clear, client_ip, is_blocked
from app.core.redis import get_redis
from app.core.security import (
    DUMMY_HASH, create_access_token, hash_password, verify_password,
)
from app.db.session import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_WINDOW = 900            # 15 menit
LOGIN_MAX_PER_PAIR = 5        # gagal per (IP, email)
LOGIN_MAX_PER_IP = 30         # gagal per IP
REGISTER_WINDOW = 3600
REGISTER_MAX_PER_IP = 10
MAX_PASSWORD_LEN = 128        # mencegah beban CPU hashing dari password raksasa


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    data: RegisterIn, request: Request,
    db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis),
):
    if not settings.allow_registration:
        raise HTTPException(403, "Pendaftaran akun baru sedang ditutup")
    key = f"register:ip:{client_ip(request)}"
    if await is_blocked(redis, key, REGISTER_MAX_PER_IP):
        raise HTTPException(429, "Terlalu banyak pendaftaran dari alamat ini. Coba lagi nanti.")
    await add_hit(redis, key, REGISTER_WINDOW)

    email = data.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "Email sudah terdaftar")
    user = User(email=email, hashed_password=hash_password(data.password),
                full_name=data.full_name.strip())
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:  # dua register bersamaan dengan email sama
        await db.rollback()
        raise HTTPException(409, "Email sudah terdaftar")
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
async def login(
    request: Request, form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis),
):
    email = form.username.lower()[:254]
    ip = client_ip(request)
    key_pair = f"login:fail:{ip}:{email}"
    key_ip = f"login:fail:ip:{ip}"
    if await is_blocked(redis, key_pair, LOGIN_MAX_PER_PAIR) or await is_blocked(
        redis, key_ip, LOGIN_MAX_PER_IP
    ):
        raise HTTPException(429, "Terlalu banyak percobaan login. Coba lagi dalam beberapa menit.")

    user = await db.scalar(select(User).where(User.email == email))
    password_ok = len(form.password) <= MAX_PASSWORD_LEN
    ok = password_ok and verify_password(form.password, user.hashed_password if user else DUMMY_HASH)
    if user is None or not ok:
        await add_hit(redis, key_pair, LOGIN_WINDOW)
        await add_hit(redis, key_ip, LOGIN_WINDOW)
        raise HTTPException(401, "Email atau password salah",
                            headers={"WWW-Authenticate": "Bearer"})
    await clear(redis, key_pair)
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
