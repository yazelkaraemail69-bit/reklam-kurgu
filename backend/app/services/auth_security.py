"""Auth güvenliği — rate limit, brute-force koruması."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class BruteForceTracker:
    """In-memory brute-force tracker — disk altında gerekirse Redis'e geç."""

    def __init__(self):
        self.attempts = {}  # {"email": [(ts, success), ...]}

    def record_attempt(self, email: str, success: bool) -> None:
        now = datetime.now(timezone.utc)
        email = email.lower()
        if email not in self.attempts:
            self.attempts[email] = []
        self.attempts[email].append((now, success))
        self.attempts[email] = [
            (ts, ok) for ts, ok in self.attempts[email]
            if (now - ts).total_seconds() < 3600
        ]

    def check_rate_limit(self, email: str, max_failures: int = 5) -> None:
        """Son 1 saatte 5+ başarısız giriş → 15 dakika kilitli."""
        email = email.lower()
        if email not in self.attempts:
            return

        now = datetime.now(timezone.utc)
        recent_failures = [
            (ts, ok) for ts, ok in self.attempts[email]
            if (now - ts).total_seconds() < 900 and not ok
        ]

        if len(recent_failures) >= max_failures:
            raise PermissionError(
                f"Çok fazla başarısız giriş. 15 dakika sonra tekrar deneyin."
            )


_tracker = BruteForceTracker()


def record_login_attempt(email: str, success: bool) -> None:
    _tracker.record_attempt(email, success)


def check_login_rate_limit(email: str) -> None:
    _tracker.check_rate_limit(email)
