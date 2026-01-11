"""MCP Tool 基类."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ToolStatus(str, Enum):
    """Tool 执行状态."""

    SUCCESS = "success"  # 执行成功
    ERROR = "error"  # 执行失败
    PENDING_CONFIRM = "pending_confirm"  # 等待用户确认


@dataclass
class ToolResult:
    """Tool 执行结果."""

    status: ToolStatus  # 执行状态
    output: str = ""  # 标准输出
    error: str = ""  # 错误信息
    exit_code: int | None = None  # 退出码
    duration_sec: float = 0.0  # 执行耗时
    metadata: dict[str, Any] | None = None  # 额外元数据

    # 确认相关
    confirm_token: str | None = None  # 确认 token
    preview: dict[str, Any] | None = None  # 确认预览信息


class MCPTool(ABC):
    """MCP Tool 基类."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool 名称."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool 描述."""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """输入 Schema（JSON Schema 格式）."""
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行 Tool.

        Args:
            **kwargs: Tool 输入参数

        Returns:
            执行结果
        """
        pass

    def to_mcp_definition(self) -> dict[str, Any]:
        """转换为 MCP Tool 定义格式.

        Returns:
            MCP Tool 定义
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolRegistry:
    """Tool 注册表."""

    def __init__(self) -> None:
        """初始化注册表."""
        self._tools: dict[str, MCPTool] = {}

    def register(self, tool: MCPTool) -> None:
        """注册 Tool.

        Args:
            tool: Tool 实例
        """
        self._tools[tool.name] = tool

    def get(self, name: str) -> MCPTool | None:
        """获取 Tool.

        Args:
            name: Tool 名称

        Returns:
            Tool 实例，或 None
        """
        return self._tools.get(name)

    def list_tools(self) -> list[MCPTool]:
        """列出所有 Tool.

        Returns:
            Tool 列表
        """
        return list(self._tools.values())

    def get_mcp_definitions(self) -> list[dict[str, Any]]:
        """获取所有 Tool 的 MCP 定义.

        Returns:
            MCP 定义列表
        """
        return [tool.to_mcp_definition() for tool in self._tools.values()]
