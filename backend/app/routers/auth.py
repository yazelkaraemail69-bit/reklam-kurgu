import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_access import has_unlimited_credits, is_admin
from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import EmailVerificationToken, PasswordResetToken, User
from app.schemas import TokenResponse, UserLogin, UserOut, UserRegister, UserUpdate
from app.security import create_access_token, hash_password, verify_password
from app.services.auth_security import check_login_rate_limit, record_login_attempt
from app.services.credits import ensure_balance_row, get_balance

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(db: Session, user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
        created_at=user.created_at,
        credits=get_balance(db, user.id),
        is_admin=is_admin(user),
        unlimited_credits=has_unlimited_credits(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> Response:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu e-posta zaten kayıtlı",
        )

    settings = get_settings()
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        preferred_language=payload.preferred_language or "tr",
        email_verified=False,
        is_admin=False,
    )
    db.add(user)
    db.flush()

    # Doğrulama token'ı üret (24 saat geçerli)
    token_value = secrets.token_urlsafe(32)
    verify_token = EmailVerificationToken(
        user_id=user.id,
        token=token_value,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(verify_token)

    ensure_balance_row(db, user, initial=settings.initial_credits)
    from app.models import CreditTransaction

    if settings.initial_credits > 0:
        db.add(
            CreditTransaction(
                user_id=user.id,
                amount=settings.initial_credits,
                reason="Kayıt bonusu",
                reference_type="signup",
                reference_id=None,
            )
        )

    db.commit()
    token = create_access_token(user.id, extra={"email": user.email})

    from fastapi.responses import JSONResponse

    response = JSONResponse(
        content=TokenResponse(access_token=token).model_dump(),
        status_code=status.HTTP_201_CREATED,
    )
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=86400,
        httponly=True,
        secure=False,
        samesite="strict",
    )
    return response


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Response:
    """Login — HttpOnly cookie'ye token set et."""
    try:
        check_login_rate_limit(payload.email.lower())
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc

    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    success = user is not None and verify_password(payload.password, user.password_hash)

    record_login_attempt(payload.email.lower(), success)

    if user is None or not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap pasif",
        )

    token = create_access_token(user.id, extra={"email": user.email})

    # Token'ı JSON + HttpOnly cookie'de döndür
    from fastapi.responses import JSONResponse

    response = JSONResponse(
        content=TokenResponse(access_token=token).model_dump(),
        status_code=status.HTTP_200_OK,
    )
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=86400,  # 24 hours
        httponly=True,  # JS'den erişilemiyor
        secure=False,  # HTTPS-only (prod'da True)
        samesite="strict",  # CSRF koruması
    )
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    return _user_out(db, user)


@router.post("/verify-email", response_model=UserOut)
def verify_email(
    token: str,
    db: Session = Depends(get_db),
) -> UserOut:
    """E-posta doğrulama token'ı ile hesapı doğrula."""
    verify_token = db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token == token)
    )
    if verify_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz doğrulama token'ı",
        )

    if verify_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doğrulama token'ı süresi dolmuş",
        )

    user = db.get(User, verify_token.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı yok")

    user.email_verified = True
    db.delete(verify_token)
    db.commit()
    db.refresh(user)
    return _user_out(db, user)


@router.post("/request-password-reset", response_model=dict)
def request_password_reset(
    email: str,
    db: Session = Depends(get_db),
) -> dict:
    """Şifre sıfırlama token'ı isteği — gerçek uygulamada e-posta gönderilmeli."""
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        return {"detail": "E-posta bulundu; link gönderildi"}

    # Eski token'ları temizle
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()

    token_value = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token_value,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(reset_token)
    db.commit()

    return {
        "detail": "Şifre sıfırlama linki e-postanıza gönderildi",
        "token_for_testing": token_value,
    }


@router.post("/reset-password", response_model=UserOut)
def reset_password(
    token: str,
    new_password: str,
    db: Session = Depends(get_db),
) -> UserOut:
    """Şifre sıfırlama — token ile yeni şifre set et."""
    reset_token = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token == token)
    )
    if reset_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz şifre sıfırlama token'ı",
        )

    if reset_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Şifre sıfırlama token'ı süresi dolmuş",
        )

    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Şifre en az 8 karakter olmalı",
        )

    user = db.get(User, reset_token.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı yok")

    user.password_hash = hash_password(new_password)
    db.delete(reset_token)
    db.commit()
    db.refresh(user)
    return _user_out(db, user)


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.preferred_language is not None:
        user.preferred_language = payload.preferred_language
    db.commit()
    db.refresh(user)
    return _user_out(db, user)
