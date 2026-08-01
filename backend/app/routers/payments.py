"""Stripe ödeme endpoint'leri."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services.payments import create_checkout_session, verify_payment

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/create-checkout-session")
def create_session(
    package_id: str = Query(..., regex="^(starter|pro|enterprise)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Stripe checkout session oluştur."""
    return create_checkout_session(db, user, package_id)


@router.post("/verify-payment")
def verify(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Ödemeyi doğrula ve kredileri ekle."""
    return verify_payment(db, user, session_id)


@router.get("/packages")
def get_packages() -> dict:
    """Mevcut kredi paketleri."""
    return {
        "packages": [
            {
                "id": "starter",
                "name": "Başlangıç Paketi",
                "credits": 100,
                "price_usd": 9.99,
                "description": "100 kredi — 1 tam Shorts pipeline",
            },
            {
                "id": "pro",
                "name": "Pro Paketi",
                "credits": 500,
                "price_usd": 39.99,
                "description": "500 kredi — 5 tam Shorts + metin + görsel",
            },
            {
                "id": "enterprise",
                "name": "Enterprise Paketi",
                "credits": 2000,
                "price_usd": 129.99,
                "description": "2000 kredi — Sınırsız kullanım (ay içinde)",
            },
        ]
    }
