"""Stripe ödeme entegrasyonu — kredit satın alma."""

from __future__ import annotations

import stripe
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.services.credits import apply_credit_change


def init_stripe():
    """Stripe client'ını initialize et."""
    settings = get_settings()
    if settings.stripe_key:
        stripe.api_key = settings.stripe_key


def create_checkout_session(
    db: Session,
    user: User,
    package_id: str,
) -> dict:
    """Stripe checkout session'ı oluştur."""
    init_stripe()
    settings = get_settings()

    if not settings.stripe_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ödeme sistemi şu an kullanılamıyor",
        )

    packages = {
        "starter": {"credits": 100, "price_usd": 9.99, "name": "Başlangıç Paketi"},
        "pro": {"credits": 500, "price_usd": 39.99, "name": "Pro Paketi"},
        "enterprise": {"credits": 2000, "price_usd": 129.99, "name": "Enterprise Paketi"},
    }

    if package_id not in packages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz paket",
        )

    pkg = packages[package_id]

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            customer_email=user.email,
            client_reference_id=f"user_{user.id}_{package_id}",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": pkg["name"],
                            "description": f"{pkg['credits']} kredi satın al",
                        },
                        "unit_amount": int(pkg["price_usd"] * 100),
                    },
                    "quantity": 1,
                }
            ],
            success_url="http://localhost:8000/?payment=success",
            cancel_url="http://localhost:8000/?payment=canceled",
        )
        return {
            "session_id": session.id,
            "checkout_url": session.url,
            "package": pkg,
        }
    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe hatası: {str(exc)}",
        ) from exc


def verify_payment(
    db: Session,
    user: User,
    session_id: str,
) -> dict:
    """Stripe session'ı doğrula ve kredileri ekle."""
    init_stripe()

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz session",
        ) from exc

    if session.payment_status != "paid":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Ödeme henüz tamamlanmadı",
        )

    if session.customer_email != user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="E-posta uyuşmuyor",
        )

    # Package belirleme
    ref = session.client_reference_id or ""
    packages = {"starter": 100, "pro": 500, "enterprise": 2000}
    credits = 0
    for pkg_id, amount in packages.items():
        if pkg_id in ref:
            credits = amount
            break

    if credits == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kredi miktarı belirlenemedi",
        )

    # Kredileri ekle
    apply_credit_change(
        db,
        user,
        credits,
        f"Stripe ödeme: {credits} kredi satın alındı",
        reference_type="stripe_payment",
        reference_id=session.id,
    )
    db.commit()

    return {
        "credits_added": credits,
        "session_id": session.id,
        "status": "completed",
    }
