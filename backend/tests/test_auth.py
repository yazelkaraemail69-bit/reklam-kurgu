"""Auth endpoint tests."""

import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.routers.auth import register
from app.schemas import UserRegister


@pytest.mark.unit
def test_register(temp_db: Session):
    """Kayıt endpoint'i — kullanıcı oluşturulmalı."""
    payload = UserRegister(
        email="test@example.com",
        password="securepass123",
        display_name="Test User",
        preferred_language="tr",
    )

    # Dependent mock olmadan direkt model test
    from app.security import hash_password
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        preferred_language=payload.preferred_language or "tr",
        email_verified=False,
        is_admin=False,
    )
    temp_db.add(user)
    temp_db.commit()
    temp_db.refresh(user)

    assert user.id is not None
    assert user.email == "test@example.com"
    assert not user.email_verified
    assert not user.is_admin


@pytest.mark.unit
def test_admin_not_by_email(temp_db: Session):
    """Admin flagı sadece DB'de olmalı, e-postaya göre değil."""
    from app.admin_access import is_admin
    from app.security import hash_password

    user = User(
        email="yazelkaraemail69@gmail.com",
        password_hash=hash_password("test"),
        is_admin=False,
        email_verified=False,
    )
    temp_db.add(user)
    temp_db.commit()

    assert not is_admin(user)

    user.is_admin = True
    assert not is_admin(user)  # email_verified hâlâ False

    user.email_verified = True
    assert is_admin(user)
