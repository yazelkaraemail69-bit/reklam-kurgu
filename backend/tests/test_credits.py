"""Credit system tests."""

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import CreditBalance, User
from app.services.credits import apply_credit_change


@pytest.mark.unit
def test_credit_deduction(temp_db: Session):
    """Kredi düşüşü — bakiye negatif olmamalı."""
    from app.security import hash_password

    user = User(
        email="test@example.com",
        password_hash=hash_password("test"),
        is_admin=False,
        email_verified=True,
    )
    temp_db.add(user)
    temp_db.commit()

    balance = CreditBalance(user_id=user.id, balance=100)
    temp_db.add(balance)
    temp_db.commit()

    # 50 kredi düş — başarı
    result = apply_credit_change(temp_db, user, -50, "test deduction")
    assert result.balance == 50

    # 100 kredi düş — başarısız
    with pytest.raises(HTTPException) as exc_info:
        apply_credit_change(temp_db, user, -100, "over limit")
    assert exc_info.value.status_code == 402


@pytest.mark.unit
def test_admin_unlimited_credits(temp_db: Session):
    """Admin kredi harcaması kaydedilir ama bakiye değişmez."""
    from app.security import hash_password

    admin = User(
        email="admin@example.com",
        password_hash=hash_password("test"),
        is_admin=True,
        email_verified=True,
    )
    temp_db.add(admin)
    temp_db.commit()

    balance = CreditBalance(user_id=admin.id, balance=0)
    temp_db.add(balance)
    temp_db.commit()

    result = apply_credit_change(temp_db, admin, -1000, "test admin unlimited")
    assert result.balance == 0  # Değişmedi
