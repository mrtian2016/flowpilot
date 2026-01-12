"""Prompts 请求处理器."""

from ..protocol import (
    PromptGetParams,
    PromptGetResult,
    PromptsListResult,
)
from ..registry import mcp_registry


async def handle_prompts_list() -> PromptsListResult:
    """处理 prompts/list 请求."""
    prompts = mcp_registry.list_prompts()
    return PromptsListResult(prompts=[p.to_definition() for p in prompts])


async def handle_prompts_get(params: PromptGetParams) -> PromptGetResult:
    """处理 prompts/get 请求."""
    prompt = mcp_registry.get_prompt(params.name)
    if not prompt:
        raise ValueError(f"Prompt '{params.name}' 未找到")

    messages = prompt.render(params.arguments)
    return PromptGetResult(
        description=prompt.description,
        messages=messages,
    )
