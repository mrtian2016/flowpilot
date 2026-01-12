"""Resources 请求处理器."""

from ..protocol import (
    ResourceContent,
    ResourceReadParams,
    ResourceReadResult,
    ResourcesListResult,
)
from ..registry import mcp_registry


async def handle_resources_list() -> ResourcesListResult:
    """处理 resources/list 请求."""
    resources = mcp_registry.list_resources()
    return ResourcesListResult(resources=[r.to_definition() for r in resources])


async def handle_resources_read(params: ResourceReadParams) -> ResourceReadResult:
    """处理 resources/read 请求."""
    resource = mcp_registry.get_resource(params.uri)
    if not resource:
        raise ValueError(f"Resource '{params.uri}' 未找到")

    content = await resource.read()
    return ResourceReadResult(
        contents=[
            ResourceContent(
                uri=resource.uri,
                mimeType=resource.mime_type,
                text=content,
            )
        ]
    )
