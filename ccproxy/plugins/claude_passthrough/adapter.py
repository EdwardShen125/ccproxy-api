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

        logger.info(
            "claude_passthrough_adapter_initialized",
            plugin="claude_passthrough",
            has_auth_manager=auth_manager is not None,
            auth_manager_type=type(auth_manager).__name__ if auth_manager else None,
            base_url=self.base_url,
            category="adapter",
        )

    async def get_target_url(self, endpoint: str) -> str:
        return f"{self.base_url}/v1/messages"

    async def prepare_provider_request(
        self, body: bytes, headers: dict[str, str], endpoint: str
    ) -> tuple[bytes, dict[str, str]]:
        # Get OAuth token
        token_value = await self._resolve_access_token()

        # Log token info (not the actual token)
        logger.debug(
            "claude_passthrough_token_resolved",
            has_token=bool(token_value),
            token_prefix=token_value[:10] + "..." if token_value else None,
            category="auth",
        )

        # Filter headers
        filtered_headers = filter_request_headers(headers, preserve_auth=False)

        # Set Authorization header
        filtered_headers["authorization"] = f"Bearer {token_value}"

        # Set required Anthropic headers
        filtered_headers["anthropic-version"] = "2023-06-01"
        # Required beta tags for OAuth-based Claude Code auth
        filtered_headers["anthropic-beta"] = "claude-code-20250219,oauth-2025-04-20"

        return body, filtered_headers

    async def process_provider_response(
        self, response: httpx.Response, endpoint: str
    ) -> Response | StreamingResponse:
        """Return the response directly without any transformation."""
        response_headers = extract_response_headers(response)

        # Log upstream response status
        logger.info(
            "claude_passthrough_upstream_response",
            status_code=response.status_code,
            upstream_url=response.url if hasattr(response, "url") else None,
            response_headers=dict(response.headers),
            category="http",
        )

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

        logger.debug(
            "claude_passthrough_resolving_token",
            token_manager_type=type(self.token_manager).__name__,
            has_load_credentials=hasattr(self.token_manager, "load_credentials"),
            has_get_access_token=hasattr(self.token_manager, "get_access_token"),
            category="auth",
        )

        # Check if credentials exist
        if hasattr(self.token_manager, "load_credentials"):
            try:
                credentials = await self.token_manager.load_credentials()
                logger.debug(
                    "claude_passthrough_credentials_loaded",
                    has_credentials=credentials is not None,
                    credentials_type=type(credentials).__name__ if credentials else None,
                    category="auth",
                )
            except Exception as exc:
                logger.warning(
                    "claude_passthrough_credentials_load_failed",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    category="auth",
                )

        async def _snapshot_token() -> str | None:
            try:
                snapshot = await self.token_manager.get_token_snapshot()
                has_snapshot = snapshot is not None
                has_access_token = snapshot and snapshot.access_token is not None
                logger.debug(
                    "claude_passthrough_snapshot",
                    has_snapshot=has_snapshot,
                    has_access_token=has_access_token,
                    category="auth",
                )
                if snapshot and snapshot.access_token:
                    return str(snapshot.access_token)
                return None
            except Exception as exc:
                logger.warning(
                    "claude_passthrough_snapshot_failed",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    category="auth",
                )
                return None

        # Try get_access_token first
        try:
            token = await self.token_manager.get_access_token()
            if token:
                logger.info(
                    "claude_passthrough_token_obtained",
                    token_manager=type(self.token_manager).__name__,
                    category="auth",
                )
                return token
        except Exception as exc:
            logger.warning(
                "claude_passthrough_get_token_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                category="auth",
            )

        # Try refresh
        try:
            refreshed = await self.token_manager.get_access_token_with_refresh()
            if refreshed:
                logger.info(
                    "claude_passthrough_token_refreshed",
                    category="auth",
                )
                return refreshed
        except OAuthTokenRefreshError as exc:
            logger.warning(
                "claude_passthrough_refresh_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                category="auth",
            )
            fallback = await _snapshot_token()
            if fallback:
                return fallback
        except Exception as exc:
            logger.warning(
                "claude_passthrough_refresh_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                category="auth",
            )

        fallback = await _snapshot_token()
        if fallback:
            return fallback

        logger.error(
            "claude_passthrough_no_valid_token",
            plugin="claude_passthrough",
            category="auth",
        )
        raise ValueError("No valid OAuth access token available for Claude Passthrough")
