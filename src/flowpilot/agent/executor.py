"""Tool 执行器 - Agent 与 Tools 的桥梁."""

import secrets
from typing import Any

from ..audit.logger import AuditLogger
from ..config.schema import FlowPilotConfig
from ..policy.engine import PolicyEngine
from ..tools.base import ToolRegistry, ToolResult, ToolStatus
from .base import LLMProvider


class ToolExecutor:
    """Tool 执行器."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        audit_logger: AuditLogger,
    ) -> None:
        """初始化执行器.

        Args:
            tool_registry: Tool 注册表
            audit_logger: 审计日志记录器
        """
        self.tool_registry = tool_registry
        self.audit_logger = audit_logger

    async def execute_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        session_id: str,
    ) -> list[dict[str, Any]]:
        """执行 Tool 调用列表.

        Args:
            tool_calls: Tool 调用列表（从 LLM 返回）
            session_id: 会话 ID

        Returns:
            Tool 执行结果列表
        """
        results = []

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["arguments"]
            tool_use_id = tool_call.get("id", secrets.token_hex(8))

            # 查找 Tool
            tool = self.tool_registry.get(tool_name)
            if not tool:
                results.append(
                    {
                        "tool_use_id": tool_use_id,
                        "error": f"Tool '{tool_name}' 未找到",
                    }
                )
                continue

            # 记录 Tool 调用
            call_id = f"call_{secrets.token_hex(8)}"
            self.audit_logger.add_tool_call(
                call_id=call_id,
                session_id=session_id,
                tool_name=tool_name,
                tool_args=tool_args,
                status="pending",
            )

            # 执行 Tool
            try:
                result = await tool.execute(**tool_args)

                # 更新审计记录
                self.audit_logger.update_tool_call(
                    call_id=call_id,
                    status=result.status.value,
                    exit_code=result.exit_code,
                    stdout_summary=result.output,
                    stderr=result.error,
                    duration_sec=result.duration_sec,
                    extra_data=result.metadata,
                )

                # 返回结果
                results.append(
                    {
                        "tool_use_id": tool_use_id,
                        "status": result.status.value,
                        "content": self._format_tool_result(result),
                        "raw_result": result,
                    }
                )

            except Exception as e:
                # 记录错误
                self.audit_logger.update_tool_call(
                    call_id=call_id,
                    status="error",
                    stderr=str(e),
                )

                results.append(
                    {
                        "tool_use_id": tool_use_id,
                        "error": f"Tool 执行失败: {str(e)}",
                    }
                )

        return results

    def _format_tool_result(self, result: ToolResult) -> str:
        """格式化 Tool 结果为文本.

        Args:
            result: Tool 执行结果

        Returns:
            格式化的文本
        """
        if result.status == ToolStatus.SUCCESS:
            return result.output

        elif result.status == ToolStatus.ERROR:
            return f"错误: {result.error}\n输出: {result.output}"

        elif result.status == ToolStatus.PENDING_CONFIRM:
            # 构造确认提示
            preview = result.preview or {}
            lines = ["⚠️  需要用户确认："]
            for key, value in preview.items():
                lines.append(f"  {key}: {value}")
            lines.append(f"\n确认 token: {result.confirm_token}")
            lines.append("请确认后使用此 token 重新调用")
            return "\n".join(lines)

        return str(result)
