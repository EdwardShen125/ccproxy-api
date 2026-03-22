"""Routes for claude-passthrough plugin."""

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, StreamingResponse

from ccproxy.api.dependencies import get_plugin_adapter
from ccproxy.auth.dependencies import ConditionalAuthDep
from ccproxy.core.logging import get_plugin_logger
from ccproxy.streaming import DeferredStreaming

from .config import ClaudePassthroughSettings


logger = get_plugin_logger()

ClaudePassthroughAdapterDep = Annotated[Any, Depends(get_plugin_adapter("claude_passthrough"))]

APIResponse = Response | StreamingResponse | DeferredStreaming


router = APIRouter()


async def _handle_adapter_request(
    request: Request,
    adapter: Any,
) -> APIResponse:
    result = await adapter.handle_request(request)
    return cast(APIResponse, result)


@router.post(
    "/v1/messages",
    response_model=None,
)
async def create_anthropic_message(
    request: Request,
    auth: ConditionalAuthDep,
    adapter: ClaudePassthroughAdapterDep,
) -> APIResponse:
    """Create a message using Claude AI - direct passthrough to Anthropic API.

    This endpoint does NOT perform any format conversion. The request body
    is passed through as-is to Anthropic API.
    """
    return await _handle_adapter_request(request, adapter)
