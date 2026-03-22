"""Simplified adapter for claude-passthrough - direct Anthropic API proxy without format conversion."""

import json
from typing import TYPE_CHECKING, Any, cast

import httpx
from starlette.responses import Response, StreamingResponse

from ccproxy.auth.exceptions import OAuthTokenRefreshError
from ccproxy.core.logging import get_plugin_logger
from ccproxy.core.plugins.interfaces import TokenManagerProtocol
from ccproxy.services.adapters.http_adapter import BaseHTTPAdapter
from ccproxy.utils.headers import extract_response_headers, filter_request_headers

if TYPE_CHECKING:
    pass


logger = get_plugin_logger()


class ClaudePassthroughAdapter(BaseHTTPAdapter):
    """Simplified Claude API adapter for passthrough - no format conversion.

    This adapter only handles OAuth authentication and passes requests directly
    to the Anthropic API without any request/response format transformation.
    """

    def __init__(
        self,
        config: "ClaudePassthroughSettings",
        auth_manager: Any | None = None,
        http_pool_manager: Any | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(config=config, auth_manager=auth_manager, http_pool_manager=http_pool_manager, **kwargs)
        self.token_manager: TokenManagerProtocol | None = auth_manager
        self.base_url = self.config.base_url.rstrip("/")

    async def get_target_url(self, endpoint: str) -> str:
        return f"{self.base_url}/v1/messages"

    async def prepare_provider_request(
        self, body: bytes, headers: dict[str, str], endpoint: str
    ) -> tuple[bytes, dict[str, str]]:
        # Get OAuth token
        token_value = await self._resolve_access_token()

        # Filter headers
        filtered_headers = filter_request_headers(headers, preserve_auth=False)

        # Set Authorization header
        filtered_headers["authorization"] = f"Bearer {token_value}"

        # Set required Anthropic headers
        filtered_headers["anthropic-version"] = "2023-06-01"

        return body, filtered_headers

    async def process_provider_response(
        self, response: httpx.Response, endpoint: str
    ) -> Response | StreamingResponse:
        """Return the response directly without any transformation."""
        response_headers = extract_response_headers(response)

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get("content-type"),
        )

    async def _resolve_access_token(self) -> str:
        """Resolve a usable Claude API OAuth token from the token manager."""
        if not self.token_manager:
            from ccproxy.core.errors import AuthenticationError

            logger.warning(
                "auth_manager_not_found",
                plugin="claude_passthrough",
                category="auth",
            )
            raise AuthenticationError(
                "Authentication manager not configured for Claude Passthrough"
            )

        async def _snapshot_token() -> str | None:
            snapshot = await self.token_manager.get_token_snapshot()
            if snapshot and snapshot.access_token:
                return str(snapshot.access_token)
            return None

        try:
            token = await self.token_manager.get_access_token()
            if token:
                return token
        except Exception as exc:
            logger.debug(
                "claude_token_fetch_failed",
                error=str(exc),
                category="auth",
            )

        # Try refresh
        try:
            refreshed = await self.token_manager.get_access_token_with_refresh()
            if refreshed:
                return refreshed
        except OAuthTokenRefreshError as exc:
            logger.warning(
                "claude_token_refresh_failed",
                error=str(exc),
                category="auth",
            )
            fallback = await _snapshot_token()
            if fallback:
                return fallback
        except Exception as exc:
            logger.debug(
                "claude_token_refresh_failed",
                error=str(exc),
                category="auth",
            )

        fallback = await _snapshot_token()
        if fallback:
            return fallback

        raise ValueError("No valid OAuth access token available for Claude Passthrough")
