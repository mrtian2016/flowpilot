"""Gemini Provider 实现 (使用新版 google.genai SDK)."""

import os
from typing import Any, AsyncIterator

from .base import LLMProvider


def _convert_proto_value(value: Any) -> Any:
    """递归转换 protobuf Struct 值为 Python 原生类型.

    Gemini API 返回的 function_call.args 是 protobuf Struct 类型，
    需要递归转换为 Python dict/list 等原生类型。

    Args:
        value: protobuf 值（可能是 Struct、MapComposite、ListValue 等）

    Returns:
        转换后的 Python 原生类型
    """
    if value is None:
        return None

    # 已经是原生类型
    if isinstance(value, (str, int, float, bool)):
        return value

    # 已经是字典，递归处理值
    if isinstance(value, dict):
        return {k: _convert_proto_value(v) for k, v in value.items()}

    # 已经是列表，递归处理元素
    if isinstance(value, list):
        return [_convert_proto_value(v) for v in value]

    # 尝试导入 protobuf 类型
    try:
        from google.protobuf.struct_pb2 import ListValue, Struct

        if isinstance(value, Struct):
            return {k: _convert_proto_value(v) for k, v in value.fields.items()}
        elif isinstance(value, ListValue):
            return [_convert_proto_value(v) for v in value.values]
    except ImportError:
        pass

    # 处理 protobuf Value 类型（HasField 方法）
    if hasattr(value, "HasField"):
        try:
            if value.HasField("string_value"):
                return value.string_value
            elif value.HasField("number_value"):
                return value.number_value
            elif value.HasField("bool_value"):
                return value.bool_value
            elif value.HasField("struct_value"):
                return _convert_proto_value(value.struct_value)
            elif value.HasField("list_value"):
                return _convert_proto_value(value.list_value)
            elif value.HasField("null_value"):
                return None
        except Exception:
            pass

    # 处理 MapComposite（类似字典的 protobuf 对象）
    if hasattr(value, "keys") and callable(value.keys):
        return {k: _convert_proto_value(value[k]) for k in value.keys()}

    # 处理可迭代对象（类似列表的 protobuf 对象）
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        try:
            return [_convert_proto_value(v) for v in value]
        except Exception:
            pass

    # 最后尝试直接转换为字典
    try:
        return dict(value)
    except (TypeError, ValueError):
        return str(value)


class GeminiProvider(LLMProvider):
    """Gemini (Google) Provider 实现 (使用新版 google.genai SDK)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.0-flash",
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> None:
        """初始化 Gemini Provider.

        Args:
            api_key: Google API Key（默认从环境变量读取）
            model: 模型名称
            max_tokens: 最大 token 数
            temperature: 温度参数
        """
        from google import genai

        self._api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Google API Key 未配置。请设置环境变量 GOOGLE_API_KEY "
                "或在初始化时传入 api_key 参数。"
            )

        self._model_name = model
        self._max_tokens = max_tokens
        self._temperature = temperature

        # 初始化客户端 (新版 SDK)
        self._client = genai.Client(api_key=self._api_key)

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
        import asyncio

        from google.genai import types

        # 提取 system instruction（如果有）
        system_instruction = None
        for msg in messages:
            if msg.get("role") == "system":
                system_instruction = msg.get("content", "")
                break

        # 转换消息格式为 Gemini contents（排除 system 消息）
        contents = self._convert_messages(messages)

        # 构建 config - 关键！system_instruction 和 tools 都要通过 config 传递
        config_kwargs: dict[str, Any] = {}

        # 系统提示词
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        # 转换 tools
        if tools:
            gemini_tools = self._convert_tools(tools)
            config_kwargs["tools"] = gemini_tools

        config = types.GenerateContentConfig(**config_kwargs)

        # 使用 asyncio.to_thread 包装同步调用
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._model_name,
            contents=contents,
            config=config,
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
        import asyncio

        from google.genai import types

        contents = self._convert_messages(messages)

        config_kwargs: dict[str, Any] = {}
        if tools:
            gemini_tools = self._convert_tools(tools)
            config_kwargs["tools"] = gemini_tools

        config = types.GenerateContentConfig(**config_kwargs)

        # 同步流式调用
        response_stream = await asyncio.to_thread(
            self._client.models.generate_content_stream,
            model=self._model_name,
            contents=contents,
            config=config,
        )

        for chunk in response_stream:
            yield self._normalize_stream_chunk(chunk)

    def _convert_messages(self, messages: list[dict[str, Any]]) -> list[Any]:
        """转换消息格式为 Gemini contents.

        Args:
            messages: 标准消息列表

        Returns:
            Gemini types.Content 列表
        """
        from google.genai import types

        contents = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # Gemini 使用 "user" 和 "model" 作为角色
            if role == "assistant":
                role = "model"

            # 处理 system 消息（Gemini 不直接支持，合并到第一条 user 消息）
            if role == "system":
                # 跳过 system 消息，由 GenerateContentConfig.system_instruction 处理
                continue

            # 处理 tool_result 消息
            if role == "user" and isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        # 转换为 function response
                        contents.append(types.Content(
                            role="function",
                            parts=[types.Part.from_function_response(
                                name=item.get("tool_use_id", "unknown"),
                                response={"result": item.get("content", "")},
                            )],
                        ))
                continue

            # 普通消息
            if isinstance(content, str):
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=content)],
                ))
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, str):
                        parts.append(types.Part.from_text(text=item))
                    elif isinstance(item, dict) and item.get("type") == "text":
                        parts.append(types.Part.from_text(text=item.get("text", "")))
                if parts:
                    contents.append(types.Content(role=role, parts=parts))

        return contents

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[Any]:
        """转换 Tool 定义为 Gemini Function Declarations 格式.

        Args:
            tools: MCP 格式的 Tool 定义 {name, description, input_schema}

        Returns:
            Gemini types.Tool 列表
        """
        from google.genai import types

        if not tools:
            return []

        function_declarations = []

        for tool in tools:
            func_decl = {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
            }

            # 转换 input_schema → parameters
            input_schema = tool.get("input_schema", {})
            if input_schema:
                func_decl["parameters"] = input_schema

            function_declarations.append(func_decl)

        # 返回 Gemini Tool 格式
        return [types.Tool(function_declarations=function_declarations)]

    def _normalize_response(self, response: Any) -> dict[str, Any]:
        """标准化响应格式.

        Args:
            response: Gemini API 响应

        Returns:
            统一格式的响应字典
        """
        text_content = ""
        tool_calls = []
        stop_reason = "stop"

        # 检查是否有候选响应
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]

            # 提取内容
            if hasattr(candidate, "content") and candidate.content:
                for part in candidate.content.parts:
                    # 文本内容
                    if hasattr(part, "text") and part.text:
                        text_content += part.text

                    # Function Call
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        # 使用递归转换函数处理嵌套的 protobuf 结构
                        args = _convert_proto_value(fc.args) if hasattr(fc, "args") and fc.args else {}

                        tool_calls.append({
                            "id": f"call_{fc.name}_{len(tool_calls)}",
                            "name": fc.name,
                            "arguments": args,
                        })

            # 检查停止原因
            if hasattr(candidate, "finish_reason"):
                finish_reason = candidate.finish_reason
                # 新版 SDK 使用字符串枚举
                if finish_reason == "STOP":
                    stop_reason = "stop"
                elif finish_reason == "MAX_TOKENS":
                    stop_reason = "max_tokens"
                elif finish_reason == "SAFETY":
                    stop_reason = "safety"
                elif tool_calls:
                    stop_reason = "tool_use"

        # 提取 usage
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "input_tokens": getattr(um, "prompt_token_count", 0) or 0,
                "output_tokens": getattr(um, "candidates_token_count", 0) or 0,
                "total_tokens": getattr(um, "total_token_count", 0) or 0,
            }

        return {
            "content": text_content,
            "tool_calls": tool_calls,
            "model": self._model_name,
            "usage": usage,
            "stop_reason": stop_reason,
            "raw_response": response,
        }

    def _normalize_stream_chunk(self, chunk: Any) -> dict[str, Any]:
        """标准化流式响应块."""
        content = ""

        if hasattr(chunk, "text") and chunk.text:
            content = chunk.text
        elif hasattr(chunk, "candidates") and chunk.candidates:
            for part in chunk.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    content += part.text

        return {
            "type": "chunk",
            "content": content,
            "data": chunk,
        }

    @property
    def supports_tool_use(self) -> bool:
        """是否支持 Tool Use."""
        return True

    @property
    def name(self) -> str:
        """Provider 名称."""
        return "gemini"

    @property
    def model(self) -> str:
        """当前使用的模型名称."""
        return self._model_name
