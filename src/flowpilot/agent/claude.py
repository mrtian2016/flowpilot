"""Claude Provider 实现."""

import os
from typing import Any, AsyncIterator

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message, ToolUseBlock

from .base import LLMProvider


class ClaudeProvider(LLMProvider):
    """Claude (Anthropic) Provider 实现."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> None:
        """初始化 Claude Provider.

        Args:
            api_key: Anthropic API Key（默认从环境变量读取）
            model: 模型名称
            max_tokens: 最大 token 数
            temperature: 温度参数
        """
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Claude API Key 未配置。请设置环境变量 ANTHROPIC_API_KEY "
                "或在初始化时传入 api_key 参数。"
            )

        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

        # 初始化客户端
        self.client = Anthropic(api_key=self._api_key)
        self.async_client = AsyncAnthropic(api_key=self._api_key)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """发送聊天请求.

        Args:
            messages: 消息列表，格式: [{"role": "user", "content": "..."}]
            tools: Tool 定义列表（MCP 格式）
            **kwargs: 额外参数（覆盖默认配置）

        Returns:
            标准化的响应字典
        """
        # 合并参数
        request_params = {
            "model": kwargs.get("model", self._model),
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
            "temperature": kwargs.get("temperature", self._temperature),
            "messages": messages,
        }

        # 添加 tools（如果有）
        if tools:
            request_params["tools"] = tools

        # 调用 API
        response: Message = await self.async_client.messages.create(**request_params)

        # 标准化返回格式
        return self._normalize_response(response)

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
        request_params = {
            "model": kwargs.get("model", self._model),
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
            "temperature": kwargs.get("temperature", self._temperature),
            "messages": messages,
        }

        if tools:
            request_params["tools"] = tools

        async with self.async_client.messages.stream(**request_params) as stream:
            async for chunk in stream:
                yield self._normalize_stream_chunk(chunk)

    def _normalize_response(self, response: Message) -> dict[str, Any]:
        """标准化响应格式.

        Args:
            response: Claude API 响应

        Returns:
            统一格式的响应字典
        """
        # 提取文本内容
        text_content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "arguments": block.input,
                    }
                )

        return {
            "content": text_content,
            "tool_calls": tool_calls,
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            "stop_reason": response.stop_reason,
            "raw_response": response,
        }

    def _normalize_stream_chunk(self, chunk: Any) -> dict[str, Any]:
        """标准化流式响应块.

        Args:
            chunk: Claude 流式响应块

        Returns:
            统一格式的响应块
        """
        # 简化实现，主要返回 chunk 类型和内容
        return {
            "type": chunk.type if hasattr(chunk, "type") else "unknown",
            "data": chunk,
        }

    @property
    def supports_tool_use(self) -> bool:
        """是否支持 Tool Use."""
        return True

    @property
    def name(self) -> str:
        """Provider 名称."""
        return "claude"

    @property
    def model(self) -> str:
        """当前使用的模型名称."""
        return self._model
