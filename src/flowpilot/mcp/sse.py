"""SSE 传输层实现."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from .protocol import JSONRPCError, JSONRPCResponse


class SSETransport:
    """SSE 传输管理器."""

    def __init__(self) -> None:
        """初始化 SSE 传输."""
        self._sessions: dict[str, asyncio.Queue[str]] = {}

    def create_session(self) -> str:
        """创建新的 SSE 会话.

        Returns:
            会话 ID
        """
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = asyncio.Queue()
        return session_id

    def remove_session(self, session_id: str) -> None:
        """移除 SSE 会话."""
        self._sessions.pop(session_id, None)

    def has_session(self, session_id: str) -> bool:
        """检查会话是否存在."""
        return session_id in self._sessions

    async def send_message(self, session_id: str, message: dict[str, Any]) -> None:
        """向会话发送消息.

        Args:
            session_id: 会话 ID
            message: 要发送的消息
        """
        if session_id in self._sessions:
            data = json.dumps(message, ensure_ascii=False)
            await self._sessions[session_id].put(f"data: {data}\n\n")

    async def send_response(self, session_id: str, request_id: str | int, result: Any) -> None:
        """发送 JSON-RPC 响应."""
        response = JSONRPCResponse(id=request_id, result=result)
        await self.send_message(session_id, response.model_dump(exclude_none=True))

    async def send_error(
        self, session_id: str, request_id: str | int | None, code: int, message: str
    ) -> None:
        """发送 JSON-RPC 错误响应."""
        response = JSONRPCResponse(
            id=request_id,
            error=JSONRPCError(code=code, message=message),
        )
        await self.send_message(session_id, response.model_dump(exclude_none=True))

    async def event_stream(self, session_id: str) -> AsyncGenerator[str, None]:
        """生成 SSE 事件流.

        Args:
            session_id: 会话 ID

        Yields:
            SSE 事件数据
        """
        if session_id not in self._sessions:
            return

        queue = self._sessions[session_id]
        try:
            while True:
                try:
                    # 带超时的等待，用于心跳
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield data
                except TimeoutError:
                    # 发送心跳保持连接
                    yield ": heartbeat\n\n"
        finally:
            self.remove_session(session_id)


# 全局 SSE 传输实例
sse_transport = SSETransport()
