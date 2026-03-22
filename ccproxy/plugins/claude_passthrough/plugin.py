"""Claude Passthrough plugin implementation."""

from typing import Any

from ccproxy.core.logging import get_plugin_logger
from ccproxy.core.plugins import (
    BaseProviderPluginFactory,
    PluginContext,
    PluginManifest,
    ProviderPluginRuntime,
)
from ccproxy.core.plugins.declaration import RouterSpec

from .adapter import ClaudePassthroughAdapter
from .config import ClaudePassthroughSettings
from .routes import router as passthrough_router
from ..oauth_claude.manager import ClaudeApiTokenManager

logger = get_plugin_logger()


class ClaudePassthroughRuntime(ProviderPluginRuntime):
    """Runtime for Claude Passthrough plugin."""

    def __init__(self, manifest: PluginManifest):
        """Initialize runtime."""
        super().__init__(manifest)
        self.config: ClaudePassthroughSettings | None = None

    async def _on_initialize(self) -> None:
        """Initialize the Claude Passthrough plugin."""
        if not self.context:
            raise RuntimeError("Context not set")

        await super()._on_initialize()

        try:
            config = self.context.get(ClaudePassthroughSettings)
        except ValueError:
            logger.warning("plugin_no_config")
            config = ClaudePassthroughSettings()
            logger.debug("plugin_using_default_config", category="plugin")

        self.config = config

        # Log credentials manager status
        credentials_manager = self.context.get("credentials_manager") if self.context else None
        has_credentials_manager = credentials_manager is not None
        credentials_manager_type = type(credentials_manager).__name__ if credentials_manager else None

        # Log token manager if available
        token_manager = None
        if credentials_manager and hasattr(credentials_manager, "token_manager"):
            token_manager = credentials_manager.token_manager
        token_manager_type = type(token_manager).__name__ if token_manager else None

        # Log authentication status
        is_authenticated = False
        if token_manager and hasattr(token_manager, "is_authenticated"):
            try:
                is_authenticated = await token_manager.is_authenticated()
            except Exception as exc:
                logger.warning(
                    "claude_passthrough_auth_check_failed",
                    error=str(exc),
                    category="auth",
                )

        logger.info(
            "claude_passthrough_initialized",
            plugin="claude_passthrough",
            version=self.manifest.version,
            status="initialized",
            base_url=self.config.base_url,
            has_credentials_manager=has_credentials_manager,
            credentials_manager_type=credentials_manager_type,
            token_manager_type=token_manager_type,
            is_authenticated=is_authenticated,
            category="plugin",
        )


class ClaudePassthroughFactory(BaseProviderPluginFactory):
    """Factory for Claude Passthrough plugin."""

    cli_safe = False

    plugin_name = "claude_passthrough"
    plugin_description = "Claude OAuth passthrough - direct Anthropic API proxy without format conversion"
    runtime_class = ClaudePassthroughRuntime
    adapter_class = ClaudePassthroughAdapter
    config_class = ClaudePassthroughSettings
    auth_manager_name = "oauth_claude"
    credentials_manager_class = ClaudeApiTokenManager
    routers = [
        RouterSpec(router=passthrough_router, prefix="/anthropic", tags=["anthropic"]),
    ]
    dependencies = ["oauth_claude"]
    optional_requires = []


factory = ClaudePassthroughFactory()

__all__ = ["ClaudePassthroughFactory", "ClaudePassthroughRuntime", "factory"]
