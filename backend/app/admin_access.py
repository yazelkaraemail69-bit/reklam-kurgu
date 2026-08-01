from app.models import User


def is_admin(user: User) -> bool:
    """DB tabanlı admin bayrağı — e-posta kimliği ile değil, is_admin kolonu ile."""
    return user.is_admin and user.email_verified


def has_unlimited_credits(user: User) -> bool:
    return is_admin(user)
