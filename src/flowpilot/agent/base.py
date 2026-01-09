"""LLM Provider 抽象基类."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class LLMProvider(ABC):
    """统一的 LLM Provider 接口."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """发送聊天请求，返回响应.

        Args:
            messages: 消息列表
            tools: Tool 定义列表（MCP 格式）
            **kwargs: 额外参数

        Returns:
            标准化的响应字典
        """
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式聊天响应.

        Args:
            messages: 消息列表
            tools: Tool 定义列表
            **kwargs: 额外参数

        Yields:
            流式响应块
        """
        yield {}  # type: ignore

    @property
    @abstractmethod
    def supports_tool_use(self) -> bool:
        """是否支持 Tool Use（Function Calling）."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """当前使用的模型名称."""
        pass
