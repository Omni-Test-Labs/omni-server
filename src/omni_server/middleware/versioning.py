"""Middleware for API version negotiation and deprecation warnings."""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from omni_server.config.versions import get_registry, Version


class VersionNegotiationMiddleware(BaseHTTPMiddleware):
    """Middleware for API version negotiation and deprecation handling."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and add version headers."""
        path = request.url.path

        if "/api/" not in path or "/graphql" in path:
            return await call_next(request)

        version = self._determine_version(request, path)
        registry = get_registry()

        request.state.api_version = version.value
        request.state.api_version_enum = version

        response = await call_next(request)

        response.headers["X-API-Version"] = version.value

        warning = registry.get_sunset_warning(version)
        if warning:
            response.headers["X-API-Deprecation-Warning"] = warning

        response.headers["X-API-Latest"] = registry.get_latest_version().value

        return response

    def _determine_version(self, request: Request, path: str) -> Version:
        """Determine API version from URL path, header, or query param."""

        version_header = request.headers.get("API-Version", "").lower()
        if version_header == "latest":
            version_header = get_registry().get_latest_version().value

        if version_header:
            return Version(version_header)

        if "/api/v1/" in path:
            return Version.V1
        if "/api/v2/" in path:
            return Version.V2
        if "/api/v3/" in path:
            return Version.V3

        return get_registry().get_latest_version()
