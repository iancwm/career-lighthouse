"""Security headers middleware for all API responses.

Adds the following headers to every response to mitigate common web attacks:

- X-Content-Type-Options: nosniff         — prevent MIME-type sniffing
- X-Frame-Options: DENY                   — block clickjacking via iframes
- X-XSS-Protection: 1; mode=block        — legacy XSS filter (belt-and-braces)
- Strict-Transport-Security               — enforce HTTPS (production only)
- Content-Security-Policy: default-src 'self'  — baseline CSP

HSTS is only emitted when the APP_ENV environment variable is set to "prod"
to avoid breaking local HTTP development.
"""

import os

from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        # Only send HSTS in production — HSTS over plain HTTP is ignored by
        # browsers but avoids confusing local dev workflows.
        if os.environ.get("APP_ENV", "").lower() == "prod":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response
