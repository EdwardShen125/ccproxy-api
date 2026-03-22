"""Configuration for claude-passthrough plugin."""

from pydantic import Field

from ccproxy.models.provider import ModelCard, ModelMappingRule, ProviderConfig


class ClaudePassthroughSettings(ProviderConfig):
    """Claude Passthrough specific configuration.

    This is a simplified configuration for direct Anthropic API proxying.
    """

    name: str = "claude-passthrough"
    base_url: str = "https://api.anthropic.com"
    supports_streaming: bool = True
    requires_auth: bool = True
    auth_type: str = "oauth"

    enabled: bool = True
    priority: int = 10

    model_mappings: list[ModelMappingRule] = Field(default_factory=list)
    models_endpoint: list[ModelCard] = Field(default_factory=list)
