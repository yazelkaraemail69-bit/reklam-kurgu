"""Güvenlik middleware — CORS, cookies, HTTPS headers."""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """HTTPS, CSP, X-Frame-Options, HSTS vb."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # HSTS — HTTPS-only (üretimde)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Clickjacking koruması
        response.headers["X-Frame-Options"] = "DENY"

        # Content-type sniffing koruması
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS koruması (eski tarayıcılar için)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # CSP — inline script'leri kapat
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "media-src 'self' https:; "
            "frame-ancestors 'none'"
        )

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response
