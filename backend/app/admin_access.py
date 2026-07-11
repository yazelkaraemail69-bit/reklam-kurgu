from app.config import get_settings
from app.models import User

# Varsayılan admin — .env boş/eksik olsa bile sen adminsin
DEFAULT_ADMIN_EMAIL = "yazelkaraemail69@gmail.com"


def is_admin(user: User) -> bool:
    """ADMIN_EMAIL ile eşleşen kullanıcı admin + sınırsız kredi."""
    admin_email = (get_settings().admin_email or "").strip().lower()
    if not admin_email:
        admin_email = DEFAULT_ADMIN_EMAIL
    return user.email.lower() == admin_email


def has_unlimited_credits(user: User) -> bool:
    return is_admin(user)
