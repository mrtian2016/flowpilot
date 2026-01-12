"""SQLAlchemy 数据模型."""

from datetime import datetime
from typing import List, Optional, Any

from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Boolean, Float, Table, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class LLMConfig(Base):
    """LLM 全局配置."""
    __tablename__ = "llm_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    default_provider: Mapped[str] = mapped_column(String, default="claude")
    
    providers: Mapped[List["LLMProvider"]] = relationship(back_populates="llm_config", cascade="all, delete-orphan")
    routing_rules: Mapped[List["RoutingRule"]] = relationship(back_populates="llm_config", cascade="all, delete-orphan")


class LLMProvider(Base):
    """LLM 提供商配置."""
    __tablename__ = "llm_providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    llm_config_id: Mapped[int] = mapped_column(ForeignKey("llm_config.id"))
    
    name: Mapped[str] = mapped_column(String)  # e.g., claude, gemini
    model: Mapped[str] = mapped_column(String)
    api_key_env: Mapped[str] = mapped_column(String)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    
    llm_config: Mapped["LLMConfig"] = relationship(back_populates="providers")


class RoutingRule(Base):
    """路由规则."""
    __tablename__ = "routing_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    llm_config_id: Mapped[int] = mapped_column(ForeignKey("llm_config.id"))
    
    scenario: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    condition: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    llm_config: Mapped["LLMConfig"] = relationship(back_populates="routing_rules")


# Host Tags Association Table
host_tags = Table(
    "host_tags",
    Base.metadata,
    Column("host_id", ForeignKey("hosts.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class Tag(Base):
    """标签."""
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    
    hosts: Mapped[List["Host"]] = relationship(secondary=host_tags, back_populates="tags")


class Host(Base):
    """主机配置."""
    __tablename__ = "hosts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True) # Alias
    
    env: Mapped[str] = mapped_column(String)
    user: Mapped[str] = mapped_column(String)
    addr: Mapped[str] = mapped_column(String)
    port: Mapped[int] = mapped_column(Integer, default=22)
    jump: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Jump host alias
    ssh_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String, default="")
    group: Mapped[str] = mapped_column(String, default="default")
    
    tags: Mapped[List["Tag"]] = relationship(secondary=host_tags, back_populates="hosts")
    host_services: Mapped[List["HostService"]] = relationship(back_populates="host", cascade="all, delete-orphan")


class JumpConfig(Base):
    """跳板机配置."""
    __tablename__ = "jumps"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True) # Jump Alias
    
    addr: Mapped[str] = mapped_column(String)
    user: Mapped[str] = mapped_column(String)
    port: Mapped[int] = mapped_column(Integer, default=22)


class HostService(Base):
    """主机服务配置 - 每台主机上运行的服务."""
    __tablename__ = "host_services"

    id: Mapped[int] = mapped_column(primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("hosts.id"))
    
    # 服务基本信息
    name: Mapped[str] = mapped_column(String)  # 用户友好名称，如 "后端服务"
    service_name: Mapped[str] = mapped_column(String)  # systemd 服务名，如 "ir_web.service"
    service_type: Mapped[str] = mapped_column(String, default="systemd")  # 类型: systemd, docker, pm2
    description: Mapped[str] = mapped_column(String, default="")
    
    # 关联主机
    host: Mapped["Host"] = relationship(back_populates="host_services")


class Service(Base):
    """服务配置."""
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    
    description: Mapped[str] = mapped_column(String, default="")
    # JSON storage for complex nested structures like hosts, logs, k8s, healthcheck due to simplicity for now
    # Since Service config is read-heavy and structure is somewhat flexible.
    # Alternatively we could normalize, but config JSON blob is often enough for "settings"
    config_json: Mapped[dict] = mapped_column(JSON) 
    
    
class PolicyRule(Base):
    """策略规则."""
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    name: Mapped[str] = mapped_column(String, unique=True)
    condition: Mapped[dict] = mapped_column(JSON) # PolicyCondition
    effect: Mapped[str] = mapped_column(String) # allow/require_confirm/deny
    message: Mapped[str] = mapped_column(String)


class AuditSession(Base):
    """审计会话记录."""

    __tablename__ = "audit_sessions"

    # 主键
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # 基本信息
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user: Mapped[str] = mapped_column(String(64))
    hostname: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # 输入输出
    input: Mapped[str] = mapped_column(Text)  # 用户输入
    input_mode: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 输入模式
    final_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 最终输出

    # Agent 推理
    agent_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Agent 推理过程
    provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 使用的 LLM Provider

    # 状态
    status: Mapped[str] = mapped_column(String(32))  # completed / failed / cancelled

    # 资源使用
    token_usage: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {input, output, total}
    total_duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 总耗时
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 成本（美元）

    # 元数据
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    tool_calls: Mapped[List["AuditToolCall"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class AuditToolCall(Base):
    """Tool 调用记录."""

    __tablename__ = "audit_tool_calls"

    # 主键
    call_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("audit_sessions.session_id"))
    
    # Tool 信息
    tool_name: Mapped[str] = mapped_column(String(64))
    tool_args: Mapped[dict] = mapped_column(JSON)

    # 策略检查
    policy_triggered: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    policy_effect: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    user_confirmed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confirm_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 执行结果
    execution_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    execution_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stdout_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 状态
    status: Mapped[str] = mapped_column(String(32))  # success / error / pending_confirm

    # 元数据
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    session: Mapped["AuditSession"] = relationship(back_populates="tool_calls")
