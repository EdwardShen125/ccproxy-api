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

        logger.debug(
            "plugin_initialized",
            plugin="claude_passthrough",
            version=self.manifest.version,
            status="initialized",
            base_url=self.config.base_url,
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
    credentials_manager_class = "ClaudeApiTokenManager"
    routers = [
        RouterSpec(router=passthrough_router, prefix="/anthropic", tags=["anthropic"]),
    ]
    dependencies = ["oauth_claude"]
    optional_requires = []


factory = ClaudePassthroughFactory()

__all__ = ["ClaudePassthroughFactory", "ClaudePassthroughRuntime", "factory"]
