"""Tools 请求处理器."""

import asyncio
import logging

from flowpilot.tools.base import ToolStatus

from ..protocol import (
    ToolCallParams,
    ToolCallResult,
    ToolContent,
    ToolDefinition,
    ToolsListResult,
)
from ..registry import mcp_registry

logger = logging.getLogger(__name__)


async def handle_tools_list() -> ToolsListResult:
    """处理 tools/list 请求."""
    tools = mcp_registry.list_tools()
    return ToolsListResult(
        tools=[
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.input_schema,
            )
            for tool in tools
        ]
    )


async def handle_tools_call(params: ToolCallParams) -> ToolCallResult:
    """处理 tools/call 请求."""
    logger.info(f"调用工具: {params.name}, 参数: {params.arguments}")

    tool = mcp_registry.get_tool(params.name)
    if not tool:
        logger.error(f"工具未找到: {params.name}")
        return ToolCallResult(
            content=[ToolContent(text=f"Tool '{params.name}' 未找到")],
            isError=True,
        )

    try:
        # 添加 60 秒超时保护
        result = await asyncio.wait_for(
            mcp_registry.call_tool(params.name, params.arguments),
            timeout=60.0,
        )
        logger.info(f"工具执行完成: {params.name}, 状态: {result.status}")

        # 转换结果
        if result.status == ToolStatus.SUCCESS:
            return ToolCallResult(
                content=[ToolContent(text=result.output)],
                isError=False,
            )
        elif result.status == ToolStatus.PENDING_CONFIRM:
            # 需要确认的情况 - 返回详细信息让 AI 知道如何处理
            preview = result.preview or {}
            confirm_text = "⚠️ 操作需要用户确认\n\n"
            confirm_text += f"原因: {preview.get('message', '安全策略要求确认')}\n"
            confirm_text += f"环境: {preview.get('env', 'unknown')}\n"
            confirm_text += f"风险级别: {preview.get('risk_level', 'unknown')}\n"
            confirm_text += f"主机: {preview.get('host_info', 'unknown')}\n"
            confirm_text += f"命令: {preview.get('command', 'unknown')}\n\n"
            confirm_text += f"确认 Token: {result.confirm_token}\n"
            confirm_text += "\n请用户确认后，使用 _confirm_token 参数重新调用此工具。"
            logger.warning(f"工具需要确认: {params.name}")
            return ToolCallResult(
                content=[ToolContent(text=confirm_text)],
                isError=False,
            )
        else:
            logger.error(f"工具执行失败: {params.name}, 错误: {result.error}")
            return ToolCallResult(
                content=[ToolContent(text=result.error or "执行失败")],
                isError=True,
            )

    except TimeoutError:
        logger.error(f"工具执行超时: {params.name} (60秒)")
        return ToolCallResult(
            content=[ToolContent(text="工具执行超时 (60秒)，可能是网络连接问题或主机无法访问")],
            isError=True,
        )
    except Exception as e:
        logger.exception(f"工具执行异常: {params.name}")
        return ToolCallResult(
            content=[ToolContent(text=f"Tool 执行异常: {e!s}")],
            isError=True,
        )
