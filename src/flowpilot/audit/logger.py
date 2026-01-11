"""审计日志记录器."""

import os
import socket
from datetime import datetime
from typing import Any

from ..utils.sensitive import mask_sensitive
from .models import AuditSession, AuditToolCall, init_database


class AuditLogger:
    """审计日志记录器."""

    def __init__(self, db_path: str = "~/.flowpilot/audit.db") -> None:
        """初始化审计日志记录器.

        Args:
            db_path: 数据库路径
        """
        self.engine, self.Session = init_database(db_path)

    def create_session(
        self,
        session_id: str,
        user_input: str,
        input_mode: str = "natural_language",
    ) -> None:
        """创建会话记录.

        Args:
            session_id: 会话 ID
            user_input: 用户输入
            input_mode: 输入模式
        """
        session = self.Session()
        try:
            record = AuditSession(
                session_id=session_id,
                timestamp=datetime.utcnow(),
                user=os.getenv("USER", "unknown"),
                hostname=socket.gethostname(),
                input=user_input,
                input_mode=input_mode,
                status="running",
            )
            session.add(record)
            session.commit()
        finally:
            session.close()

    def update_session(
        self,
        session_id: str,
        **kwargs: Any,
    ) -> None:
        """更新会话记录.

        Args:
            session_id: 会话 ID
            **kwargs: 要更新的字段
        """
        session = self.Session()
        try:
            record = session.query(AuditSession).filter_by(session_id=session_id).first()
            if record:
                for key, value in kwargs.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
                session.commit()
        finally:
            session.close()

    def add_tool_call(
        self,
        call_id: str,
        session_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        status: str = "pending",
    ) -> None:
        """添加 Tool 调用记录.

        Args:
            call_id: 调用 ID
            session_id: 会话 ID
            tool_name: Tool 名称
            tool_args: Tool 参数
            status: 状态
        """
        session = self.Session()
        try:
            record = AuditToolCall(
                call_id=call_id,
                session_id=session_id,
                tool_name=tool_name,
                tool_args=tool_args,
                status=status,
            )
            session.add(record)
            session.commit()
        finally:
            session.close()

    def update_tool_call(
        self,
        call_id: str,
        **kwargs: Any,
    ) -> None:
        """更新 Tool 调用记录.

        Args:
            call_id: 调用 ID
            **kwargs: 要更新的字段（会自动脱敏 stdout_summary）
        """
        session = self.Session()
        try:
            record = session.query(AuditToolCall).filter_by(call_id=call_id).first()
            if record:
                for key, value in kwargs.items():
                    # 脱敏处理
                    if key == "stdout_summary" and isinstance(value, str):
                        value = mask_sensitive(value)
                    if hasattr(record, key):
                        setattr(record, key, value)
                session.commit()
        finally:
            session.close()

    def get_recent_sessions(self, limit: int = 10, env: str | None = None) -> list[dict[str, Any]]:
        """获取最近的会话记录.

        Args:
            limit: 返回数量
            env: 环境过滤（可选）

        Returns:
            会话记录列表
        """
        session = self.Session()
        try:
            query = session.query(AuditSession).order_by(AuditSession.timestamp.desc())

            # TODO: 添加环境过滤（需要在 metadata 中存储 env）

            records = query.limit(limit).all()

            return [
                {
                    "session_id": r.session_id,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "user": r.user,
                    "input": r.input,
                    "status": r.status,
                    "duration_sec": r.total_duration_sec,
                }
                for r in records
            ]
        finally:
            session.close()

    def get_session_details(self, session_id: str) -> dict[str, Any] | None:
        """获取会话详情（含 Tool 调用）.

        Args:
            session_id: 会话 ID

        Returns:
            会话详情，或 None
        """
        session = self.Session()
        try:
            # 查询会话
            sess_record = session.query(AuditSession).filter_by(session_id=session_id).first()
            if not sess_record:
                return None

            # 查询 Tool 调用
            tool_calls = session.query(AuditToolCall).filter_by(session_id=session_id).all()

            return {
                "session_id": sess_record.session_id,
                "timestamp": sess_record.timestamp.isoformat() if sess_record.timestamp else None,
                "user": sess_record.user,
                "hostname": sess_record.hostname,
                "input": sess_record.input,
                "final_output": sess_record.final_output,
                "status": sess_record.status,
                "provider": sess_record.provider,
                "duration_sec": sess_record.total_duration_sec,
                "tool_calls": [
                    {
                        "call_id": tc.call_id,
                        "tool_name": tc.tool_name,
                        "tool_args": tc.tool_args,
                        "status": tc.status,
                        "exit_code": tc.exit_code,
                        "duration_sec": tc.duration_sec,
                    }
                    for tc in tool_calls
                ],
            }
        finally:
            session.close()
