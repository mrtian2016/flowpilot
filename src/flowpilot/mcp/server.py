"""FastAPI MCP Server 主入口."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .handlers import (
    handle_prompts_get,
    handle_prompts_list,
    handle_resources_list,
    handle_resources_read,
    handle_tools_call,
    handle_tools_list,
)
from .openai_compat import openai_router
from .rest_api import rest_router
from .protocol import (
    InitializeResult,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    MCPErrorCode,
    PromptGetParams,
    ResourceReadParams,
    ToolCallParams,
)
from .registry import mcp_registry
from .sse import sse_transport

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[misc]
    """应用生命周期管理."""
    # 启动时初始化
    logger.info("初始化 MCP Registry...")
    mcp_registry.initialize()
    logger.info(f"已注册 {len(mcp_registry.list_tools())} 个 Tools")
    logger.info(f"已注册 {len(mcp_registry.list_resources())} 个 Resources")
    logger.info(f"已注册 {len(mcp_registry.list_prompts())} 个 Prompts")
    yield
    # 关闭时清理
    logger.info("MCP Server 关闭")


app = FastAPI(
    title="FlowPilot MCP Server",
    description="MCP Server for FlowPilot DevOps Agent",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 OpenAI 兼容接口
app.include_router(openai_router, prefix="")

# 挂载 REST API
app.include_router(rest_router, prefix="")


# ========== SSE 端点 ==========
@app.get("/sse")
async def sse_endpoint(request: Request) -> StreamingResponse:
    """SSE 连接端点."""
    session_id = sse_transport.create_session()
    logger.info(f"新建 SSE 会话: {session_id}")

    async def event_generator():  # type: ignore[misc]
        # 发送会话建立事件
        yield f"event: endpoint\ndata: /message?session_id={session_id}\n\n"

        async for event in sse_transport.event_stream(session_id):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ========== 消息处理端点 ==========
@app.post("/message")
async def message_endpoint(request: Request, session_id: str) -> JSONResponse:
    """JSON-RPC 消息处理端点."""
    try:
        body = await request.json()
        rpc_request = JSONRPCRequest(**body)
    except Exception as e:
        logger.error(f"请求解析失败: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e

    # 通知消息（没有 id）不需要响应
    if rpc_request.is_notification:
        logger.debug(f"收到通知: {rpc_request.method}")
        # 处理通知但不返回响应
        try:
            await dispatch_request(rpc_request)
        except Exception as e:
            logger.warning(f"通知处理失败: {e}")
        return JSONResponse(content={"status": "ok"})

    # 分发请求
    try:
        result = await dispatch_request(rpc_request)
        response = JSONRPCResponse(id=rpc_request.id, result=result)
    except ValueError as e:
        response = JSONRPCResponse(
            id=rpc_request.id,
            error=JSONRPCError(
                code=MCPErrorCode.INVALID_PARAMS,
                message=str(e),
            ),
        )
    except Exception as e:
        logger.exception(f"请求处理异常: {e}")
        response = JSONRPCResponse(
            id=rpc_request.id,
            error=JSONRPCError(
                code=MCPErrorCode.INTERNAL_ERROR,
                message=str(e),
            ),
        )

    # 通过 SSE 发送响应
    if sse_transport.has_session(session_id):
        await sse_transport.send_message(session_id, response.model_dump(exclude_none=True))

    # 同时返回 HTTP 响应
    return JSONResponse(content=response.model_dump(exclude_none=True))


async def dispatch_request(request: JSONRPCRequest) -> Any:
    """分发 JSON-RPC 请求."""
    method = request.method
    params = request.params or {}

    # 初始化
    if method == "initialize":
        return InitializeResult().model_dump()

    elif method == "initialized" or method == "notifications/initialized":
        return {}

    # Tools
    elif method == "tools/list":
        result = await handle_tools_list()
        return result.model_dump()

    elif method == "tools/call":
        call_params = ToolCallParams(**params)
        result = await handle_tools_call(call_params)
        return result.model_dump()

    # Resources
    elif method == "resources/list":
        result = await handle_resources_list()
        return result.model_dump()

    elif method == "resources/read":
        read_params = ResourceReadParams(**params)
        result = await handle_resources_read(read_params)
        return result.model_dump()

    # Prompts
    elif method == "prompts/list":
        result = await handle_prompts_list()
        return result.model_dump()

    elif method == "prompts/get":
        get_params = PromptGetParams(**params)
        result = await handle_prompts_get(get_params)
        return result.model_dump()

    # 未知方法
    else:
        raise ValueError(f"未知方法: {method}")


# ========== 健康检查 ==========
@app.get("/health")
async def health_check() -> dict[str, Any]:
    """健康检查端点."""
    return {
        "status": "healthy",
        "tools_count": len(mcp_registry.list_tools()),
        "resources_count": len(mcp_registry.list_resources()),
        "prompts_count": len(mcp_registry.list_prompts()),
    }
