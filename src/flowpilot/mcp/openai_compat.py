"""OpenAI 兼容 API 模块.

将 FlowPilot 的多 LLM 提供商封装为 OpenAI 标准接口。
支持工具调用和 Agent 循环。
"""

import json
import logging
import os
import time
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from flowpilot.agent.conversation import SYSTEM_PROMPT
from flowpilot.agent.router import ProviderRouter
from flowpilot.config.loader import ConfigLoader

from .registry import mcp_registry

logger = logging.getLogger(__name__)

# ========== Pydantic 模型 ==========


class ChatMessage(BaseModel):
    """聊天消息."""

    role: str = Field(..., description="消息角色: system, user, assistant, tool")
    content: str | None = Field(None, description="消息内容")
    name: str | None = Field(None, description="发送者名称（可选）")
    tool_calls: list[dict[str, Any]] | None = Field(None, description="工具调用")
    tool_call_id: str | None = Field(None, description="工具调用 ID (tool 角色时必需)")


class ChatCompletionRequest(BaseModel):
    """聊天补全请求 (OpenAI 格式)."""

    model: str = Field(..., description="模型名称: claude, gemini, zhipu")
    messages: list[ChatMessage] = Field(..., description="消息列表")
    temperature: float | None = Field(None, ge=0, le=2, description="温度参数")
    max_tokens: int | None = Field(None, gt=0, description="最大 token 数")
    stream: bool = Field(False, description="是否流式响应")
    top_p: float | None = Field(None, ge=0, le=1, description="Top-p 采样")
    n: int = Field(1, ge=1, description="生成数量")
    stop: str | list[str] | None = Field(None, description="停止标记")
    user: str | None = Field(None, description="用户标识")
    # FlowPilot 扩展参数
    tools: bool = Field(True, description="是否启用工具 (FlowPilot 扩展)")
    max_iterations: int = Field(10, ge=1, le=20, description="最大 Agent 迭代次数")


class Usage(BaseModel):
    """Token 使用统计."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ToolCall(BaseModel):
    """工具调用."""

    id: str
    type: str = "function"
    function: dict[str, Any]


class ChatCompletionChoice(BaseModel):
    """补全选项."""

    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    """聊天补全响应 (OpenAI 格式)."""

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage


class ChatCompletionChunkChoice(BaseModel):
    """流式响应选项."""

    index: int = 0
    delta: dict[str, Any]
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    """流式响应块 (OpenAI 格式)."""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice]


class ModelInfo(BaseModel):
    """模型信息."""

    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "flowpilot"


class ModelListResponse(BaseModel):
    """模型列表响应."""

    object: str = "list"
    data: list[ModelInfo]


# ========== 认证 ==========

security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """验证 API Key.

    支持两种来源:
    1. 环境变量 FLOWPILOT_API_KEY
    2. Bearer Token (任意非空即可，用于开放测试)
    """
    expected_key = os.getenv("FLOWPILOT_API_KEY")

    if expected_key:
        # 如果设置了 API Key，严格验证
        if not credentials or credentials.credentials != expected_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return credentials.credentials

    # 如果未设置 API Key，接受任意 Bearer Token (方便测试)
    if credentials and credentials.credentials:
        return credentials.credentials

    # 无认证也允许 (开发模式)
    return "anonymous"


# ========== Router ==========

openai_router = APIRouter(tags=["OpenAI Compatible"])


def _get_provider_router() -> ProviderRouter:
    """获取 Provider 路由器 (每次请求重新加载配置)."""
    loader = ConfigLoader()
    config = loader.load()
    return ProviderRouter(config.llm)


def _get_tools_definitions() -> list[dict[str, Any]]:
    """获取所有工具的 MCP 定义."""
    # 确保 registry 已初始化
    if not mcp_registry._initialized:
        mcp_registry.initialize()
    
    tools = mcp_registry.list_tools()
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in tools
    ]


@openai_router.get("/v1/models")
async def list_models(api_key: str = Depends(verify_api_key)) -> ModelListResponse:
    """列出可用模型 (OpenAI 兼容).

    返回 FlowPilot 支持的所有 LLM 提供商作为模型。
    """
    router = _get_provider_router()
    providers = router.list_providers()

    models = [ModelInfo(id=p) for p in providers]

    return ModelListResponse(data=models)


@openai_router.get("/v1/tools")
async def list_tools(api_key: str = Depends(verify_api_key)) -> dict[str, Any]:
    """列出可用工具 (FlowPilot 扩展).
    
    返回所有注册的 MCP 工具。
    """
    tools = _get_tools_definitions()
    return {
        "object": "list",
        "data": tools,
    }


@openai_router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: ChatCompletionRequest,
    api_key: str = Depends(verify_api_key),
):
    """聊天补全 (OpenAI 兼容).

    将请求转发给指定的 LLM 提供商。
    支持工具调用和 Agent 循环。
    """
    # 获取 Provider
    router = _get_provider_router()

    try:
        provider = router.get_provider(provider_name=request.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # 转换消息格式
    messages = _convert_messages(request.messages)

    # 获取工具定义
    tools = _get_tools_definitions()

    # 流式响应暂不支持工具调用
    if request.stream:
        return StreamingResponse(
            _stream_chat(provider, messages, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 非流式响应 - Agent 循环
    try:
        final_response = await _agent_loop(
            provider=provider,
            messages=messages,
            tools=tools,
            max_iterations=request.max_iterations,
        )
    except Exception as e:
        logger.exception(f"Agent 循环失败: {e}")
        raise HTTPException(status_code=500, detail=f"LLM 调用失败: {e}") from e

    # 构建响应
    usage = final_response.get("usage", {})
    tool_calls_data = final_response.get("tool_calls", [])
    
    # 构建消息
    msg = ChatMessage(
        role="assistant", 
        content=final_response.get("content", ""),
    )
    
    # 如果有未执行的工具调用（max_iterations 达到），返回工具调用
    if tool_calls_data and final_response.get("stop_reason") == "tool_use":
        msg.tool_calls = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc.get("arguments", {})),
                }
            }
            for tc in tool_calls_data
        ]
    
    choice = ChatCompletionChoice(
        index=0,
        message=msg,
        finish_reason=_convert_stop_reason(final_response.get("stop_reason", "stop")),
    )

    return ChatCompletionResponse(
        model=request.model,
        choices=[choice],
        usage=Usage(
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        ),
    )


def _convert_messages(messages: list[ChatMessage], inject_system_prompt: bool = True) -> list[dict[str, Any]]:
    """将 OpenAI 格式消息转换为内部格式.
    
    Args:
        messages: OpenAI 格式的消息列表
        inject_system_prompt: 是否注入 FlowPilot 系统提示词
    """
    result = []
    
    # 检查是否已有 system 消息
    has_system = any(msg.role == "system" for msg in messages)
    
    # 如果没有 system 消息且需要注入，添加 FlowPilot 系统提示词
    if inject_system_prompt and not has_system:
        result.append({"role": "system", "content": SYSTEM_PROMPT})
    
    for msg in messages:
        converted = {"role": msg.role, "content": msg.content or ""}
        
        # 处理 tool 消息 -> tool_result
        if msg.role == "tool" and msg.tool_call_id:
            converted = {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content or "",
                    }

                ],
            }
        
        result.append(converted)
    return result


async def _agent_loop(
    provider: Any,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    max_iterations: int,
) -> dict[str, Any]:
    """执行 Agent 循环.
    
    循环调用 LLM 并执行工具，直到:
    1. LLM 返回最终文本响应 (无工具调用)
    2. 达到最大迭代次数
    """
    conversation = messages.copy()
    final_response = None
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    
    for iteration in range(max_iterations):
        logger.debug(f"Agent 循环 iteration {iteration + 1}/{max_iterations}")
        
        # 调用 LLM
        response = await provider.chat(messages=conversation, tools=tools)
        
        # 累加 token 使用
        usage = response.get("usage", {})
        total_usage["input_tokens"] += usage.get("input_tokens", 0)
        total_usage["output_tokens"] += usage.get("output_tokens", 0)
        total_usage["total_tokens"] += usage.get("total_tokens", 0)
        
        # 检查是否有工具调用
        tool_calls = response.get("tool_calls", [])
        
        if not tool_calls:
            # 无工具调用，返回最终响应
            response["usage"] = total_usage
            return response
        
        # 执行工具调用
        logger.info(f"执行 {len(tool_calls)} 个工具调用")
        
        # 添加 assistant 消息 (包含工具调用)
        assistant_content = response.get("content", "")
        conversation.append({
            "role": "assistant",
            "content": assistant_content,
        })
        
        # 执行每个工具并添加结果
        tool_results = []
        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc.get("arguments", {})
            tool_id = tc.get("id", f"call_{tool_name}")
            
            try:
                logger.debug(f"调用工具: {tool_name}({tool_args})")
                result = await mcp_registry.call_tool(tool_name, tool_args)
                
                # 正确处理 ToolResult - 同时考虑 status、output 和 error
                if hasattr(result, 'status'):
                    from flowpilot.tools.base import ToolStatus
                    if result.status == ToolStatus.ERROR:
                        # 错误情况：优先返回 error 字段
                        result_text = result.error or result.output or "工具执行失败（无详细错误信息）"
                    elif result.status == ToolStatus.PENDING_CONFIRM:
                        # 需要确认：返回预览信息
                        result_text = f"⚠️ 需要确认: {result.preview}" if result.preview else "需要用户确认"
                    else:
                        # 成功：返回 output，如有 error 也附加
                        result_text = result.output or ""
                        if result.error:
                            result_text += f"\n[stderr]: {result.error}"
                else:
                    result_text = str(result)
            except Exception as e:
                logger.error(f"工具调用失败: {tool_name}: {e}")
                result_text = f"错误: {e}"
            
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result_text,
            })
        
        # 添加工具结果到对话
        conversation.append({
            "role": "user",
            "content": tool_results,
        })
        
        final_response = response
    
    # 达到最大迭代次数
    logger.warning(f"达到最大迭代次数 {max_iterations}")
    if final_response:
        final_response["usage"] = total_usage
        final_response["content"] = final_response.get("content", "") + f"\n\n⚠️ 达到最大迭代次数 ({max_iterations})，任务可能未完成。"
    else:
        final_response = {
            "content": f"⚠️ 达到最大迭代次数 ({max_iterations})",
            "tool_calls": [],
            "usage": total_usage,
            "stop_reason": "stop",
        }
    
    return final_response


async def _stream_chat(
    provider: Any,
    messages: list[dict[str, Any]],
    request: ChatCompletionRequest,
) -> AsyncIterator[str]:
    """流式聊天响应生成器 (暂不支持工具调用)."""
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    try:
        # 发送首个 chunk（带 role）
        first_chunk = ChatCompletionChunk(
            id=chunk_id,
            created=created,
            model=request.model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta={"role": "assistant"},
                    finish_reason=None,
                )
            ],
        )
        yield f"data: {first_chunk.model_dump_json()}\n\n"

        # 流式获取内容 (不使用工具)
        async for chunk in provider.stream_chat(messages=messages, tools=None):
            content = chunk.get("content", "")
            if content:
                stream_chunk = ChatCompletionChunk(
                    id=chunk_id,
                    created=created,
                    model=request.model,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta={"content": content},
                            finish_reason=None,
                        )
                    ],
                )
                yield f"data: {stream_chunk.model_dump_json()}\n\n"

        # 发送结束 chunk
        final_chunk = ChatCompletionChunk(
            id=chunk_id,
            created=created,
            model=request.model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta={},
                    finish_reason="stop",
                )
            ],
        )
        yield f"data: {final_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        # 发送错误信息
        error_data = {"error": {"message": str(e), "type": "server_error"}}
        yield f"data: {json.dumps(error_data)}\n\n"


def _convert_stop_reason(reason: str) -> str:
    """转换停止原因为 OpenAI 格式."""
    mapping = {
        "stop": "stop",
        "end_turn": "stop",
        "max_tokens": "length",
        "tool_use": "tool_calls",
        "safety": "content_filter",
    }
    return mapping.get(reason, "stop")
