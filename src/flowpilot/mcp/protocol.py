"""MCP 协议消息定义."""

from enum import IntEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ========== JSON-RPC 基础 ==========
class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 请求（包含通知，通知没有 id）."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None  # 通知消息没有 id
    method: str
    params: dict[str, Any] | None = None

    @property
    def is_notification(self) -> bool:
        """是否为通知消息（没有 id）."""
        return self.id is None


class JSONRPCError(BaseModel):
    """JSON-RPC 错误."""

    code: int
    message: str
    data: Any | None = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 响应."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None
    result: Any | None = None
    error: JSONRPCError | None = None


# ========== MCP 错误码 ==========
class MCPErrorCode(IntEnum):
    """MCP 错误码."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # MCP 特定错误
    RESOURCE_NOT_FOUND = -32001
    TOOL_NOT_FOUND = -32002
    PROMPT_NOT_FOUND = -32003


# ========== MCP 初始化 ==========
class ClientInfo(BaseModel):
    """客户端信息."""

    name: str
    version: str


class ServerInfo(BaseModel):
    """服务器信息."""

    name: str = "flowpilot-mcp-server"
    version: str = "0.1.0"


class ServerCapabilities(BaseModel):
    """服务器能力声明."""

    tools: dict[str, Any] | None = Field(default_factory=lambda: {"listChanged": True})
    resources: dict[str, Any] | None = Field(
        default_factory=lambda: {"subscribe": False, "listChanged": True}
    )
    prompts: dict[str, Any] | None = Field(default_factory=lambda: {"listChanged": True})


class InitializeParams(BaseModel):
    """initialize 请求参数."""

    protocolVersion: str
    capabilities: dict[str, Any]
    clientInfo: ClientInfo


class InitializeResult(BaseModel):
    """initialize 响应结果."""

    protocolVersion: str = "2024-11-05"
    capabilities: ServerCapabilities = Field(default_factory=ServerCapabilities)
    serverInfo: ServerInfo = Field(default_factory=ServerInfo)


# ========== Tools ==========
class ToolDefinition(BaseModel):
    """Tool 定义."""

    name: str
    description: str
    inputSchema: dict[str, Any]


class ToolsListResult(BaseModel):
    """tools/list 结果."""

    tools: list[ToolDefinition]


class ToolCallParams(BaseModel):
    """tools/call 参数."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolContent(BaseModel):
    """Tool 执行内容."""

    type: Literal["text", "image", "resource"] = "text"
    text: str | None = None
    data: str | None = None  # base64 for image
    mimeType: str | None = None


class ToolCallResult(BaseModel):
    """tools/call 结果."""

    content: list[ToolContent]
    isError: bool = False


# ========== Resources ==========
class ResourceDefinition(BaseModel):
    """Resource 定义."""

    uri: str
    name: str
    description: str | None = None
    mimeType: str = "application/json"


class ResourcesListResult(BaseModel):
    """resources/list 结果."""

    resources: list[ResourceDefinition]


class ResourceReadParams(BaseModel):
    """resources/read 参数."""

    uri: str


class ResourceContent(BaseModel):
    """Resource 内容."""

    uri: str
    mimeType: str = "application/json"
    text: str | None = None
    blob: str | None = None  # base64


class ResourceReadResult(BaseModel):
    """resources/read 结果."""

    contents: list[ResourceContent]


# ========== Prompts ==========
class PromptArgument(BaseModel):
    """Prompt 参数定义."""

    name: str
    description: str | None = None
    required: bool = False


class PromptDefinition(BaseModel):
    """Prompt 定义."""

    name: str
    description: str | None = None
    arguments: list[PromptArgument] | None = None


class PromptsListResult(BaseModel):
    """prompts/list 结果."""

    prompts: list[PromptDefinition]


class PromptGetParams(BaseModel):
    """prompts/get 参数."""

    name: str
    arguments: dict[str, str] | None = None


class TextContent(BaseModel):
    """文本内容."""

    type: Literal["text"] = "text"
    text: str


class ImageContent(BaseModel):
    """图片内容."""

    type: Literal["image"] = "image"
    data: str
    mimeType: str


class PromptMessage(BaseModel):
    """Prompt 消息."""

    role: Literal["user", "assistant"]
    content: TextContent | ImageContent | ResourceContent


class PromptGetResult(BaseModel):
    """prompts/get 结果."""

    description: str | None = None
    messages: list[PromptMessage]
