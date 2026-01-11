"""审计日志数据模型."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class AuditSession(Base):
    """审计会话记录."""

    __tablename__ = "sessions"

    # 主键
    session_id = Column(String(64), primary_key=True)

    # 基本信息
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    user = Column(String(64), nullable=False)
    hostname = Column(String(128))

    # 输入输出
    input = Column(Text, nullable=False)  # 用户输入
    input_mode = Column(String(32))  # 输入模式: natural_language / structured
    final_output = Column(Text)  # 最终输出

    # Agent 推理
    agent_reasoning = Column(Text)  # Agent 推理过程
    provider = Column(String(32))  # 使用的 LLM Provider

    # 状态
    status = Column(String(32), nullable=False)  # completed / failed / cancelled

    # 资源使用
    token_usage = Column(JSON)  # {input, output, total}
    total_duration_sec = Column(Float)  # 总耗时
    cost_usd = Column(Float)  # 成本（美元）

    # 元数据（避免与 SQLAlchemy 保留字冲突）
    extra_data = Column(JSON)  # 额外元数据


class AuditToolCall(Base):
    """Tool 调用记录."""

    __tablename__ = "tool_calls"

    # 主键
    call_id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)  # 关联会话

    # Tool 信息
    tool_name = Column(String(64), nullable=False)
    tool_args = Column(JSON, nullable=False)  # Tool 参数

    # 策略检查
    policy_triggered = Column(String(128))  # 触发的策略名称
    policy_effect = Column(String(32))  # allow / require_confirm / deny
    user_confirmed = Column(Integer)  # 是否用户确认（0/1）
    confirm_time = Column(DateTime)  # 确认时间

    # 执行结果
    execution_start = Column(DateTime)
    execution_end = Column(DateTime)
    exit_code = Column(Integer)
    stdout_summary = Column(Text)  # 脱敏后的输出摘要
    stderr = Column(Text)
    duration_sec = Column(Float)

    # 状态
    status = Column(String(32), nullable=False)  # success / error / pending_confirm

    # 元数据（避免与 SQLAlchemy 保留字冲突）
    extra_data = Column(JSON)


def init_database(db_path: str = "~/.flowpilot/audit.db") -> tuple[Any, Any]:
    """初始化数据库.

    Args:
        db_path: 数据库文件路径

    Returns:
        (engine, Session)
    """
    import os

    db_path = os.path.expanduser(db_path)

    # 创建目录（如果不存在）
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # 创建引擎
    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    # 创建表
    Base.metadata.create_all(engine)

    # 创建 Session
    Session = sessionmaker(bind=engine)

    return engine, Session
