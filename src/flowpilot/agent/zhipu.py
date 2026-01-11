"""智谱 (GLM) Provider 实现."""

import asyncio
import json
import os
from typing import Any, AsyncIterator

from zhipuai import ZhipuAI

from .base import LLMProvider


class ZhipuProvider(LLMProvider):
    """智谱 (GLM) Provider 实现.

    智谱 API 与 OpenAI 格式兼容，Tool 使用 OpenAI 的 function calling 格式。
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "glm-4-plus",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> None:
        """初始化智谱 Provider.

        Args:
            api_key: 智谱 API Key（默认从环境变量读取）
            model: 模型名称
            max_tokens: 最大 token 数
            temperature: 温度参数
        """
        self._api_key = api_key or os.getenv("ZHIPU_API_KEY")
        if not self._api_key:
            raise ValueError(
                "智谱 API Key 未配置。请设置环境变量 ZHIPU_API_KEY "
                "或在初始化时传入 api_key 参数。"
            )

        self._model_name = model
        self._max_tokens = max_tokens
        self._temperature = temperature

        # 初始化客户端
        self.client = ZhipuAI(api_key=self._api_key)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """发送聊天请求.

        Args:
            messages: 消息列表
            tools: Tool 定义列表（MCP 格式）
            **kwargs: 额外参数

        Returns:
            标准化的响应字典
        """
        request_params = {
            "model": kwargs.get("model", self._model_name),
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
            "temperature": kwargs.get("temperature", self._temperature),
        }

        # 添加 tools（转换为 OpenAI 格式）
        if tools:
            request_params["tools"] = self._convert_tools(tools)
            request_params["tool_choice"] = "auto"

        # 使用 asyncio.to_thread 包装同步调用
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            **request_params,
        )

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
            "model": kwargs.get("model", self._model_name),
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
            "temperature": kwargs.get("temperature", self._temperature),
            "stream": True,
        }

        if tools:
            request_params["tools"] = self._convert_tools(tools)

        # 在线程中执行同步流式调用
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            **request_params,
        )

        # 异步迭代流式响应
        for chunk in response:
            yield self._normalize_stream_chunk(chunk)

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """转换 Tool 定义为智谱/OpenAI 格式.

        Args:
            tools: MCP 格式的 Tool 定义
                {name, description, input_schema}

        Returns:
            OpenAI 格式的 Tool 定义
                {type: "function", function: {name, description, parameters}}
        """
        converted = []

        for tool in tools:
            converted.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                },
            })

        return converted

    def _normalize_response(self, response: Any) -> dict[str, Any]:
        """标准化响应格式.

        Args:
            response: 智谱 API 响应

        Returns:
            统一格式的响应字典
        """
        choice = response.choices[0] if response.choices else None

        if not choice:
            return {
                "content": "",
                "tool_calls": [],
                "model": self._model_name,
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "stop_reason": "error",
                "raw_response": response,
            }

        # 提取内容
        message = choice.message
        text_content = message.content if hasattr(message, "content") and message.content else ""

        # 提取 tool calls
        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tool_call in message.tool_calls:
                # 解析 arguments（可能是 JSON 字符串）
                arguments = tool_call.function.arguments
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {"raw": arguments}

                tool_calls.append({
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "arguments": arguments,
                })

        # 确定停止原因
        stop_reason = "stop"
        if hasattr(choice, "finish_reason"):
            if choice.finish_reason == "tool_calls":
                stop_reason = "tool_use"
            elif choice.finish_reason == "length":
                stop_reason = "max_tokens"
            else:
                stop_reason = choice.finish_reason or "stop"

        return {
            "content": text_content,
            "tool_calls": tool_calls,
            "model": getattr(response, "model", self._model_name),
            "usage": {
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            "stop_reason": stop_reason,
            "raw_response": response,
        }

    def _normalize_stream_chunk(self, chunk: Any) -> dict[str, Any]:
        """标准化流式响应块."""
        choice = chunk.choices[0] if chunk.choices else None
        content = ""
        tool_call_delta = None

        if choice and hasattr(choice, "delta"):
            delta = choice.delta
            if hasattr(delta, "content") and delta.content:
                content = delta.content

            # 处理流式 tool call
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                tc = delta.tool_calls[0]
                tool_call_delta = {
                    "index": tc.index if hasattr(tc, "index") else 0,
                    "id": tc.id if hasattr(tc, "id") else None,
                    "name": tc.function.name if hasattr(tc.function, "name") else None,
                    "arguments": tc.function.arguments if hasattr(tc.function, "arguments") else "",
                }

        return {
            "type": "chunk",
            "content": content,
            "tool_call": tool_call_delta,
            "data": chunk,
        }

    @property
    def supports_tool_use(self) -> bool:
        """是否支持 Tool Use."""
        return True

    @property
    def name(self) -> str:
        """Provider 名称."""
        return "zhipu"

    @property
    def model(self) -> str:
        """当前使用的模型名称."""
        return self._model_name
