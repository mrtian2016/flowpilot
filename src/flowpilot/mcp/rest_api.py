"""REST API 路由模块.

提供数据库 CRUD 操作的 REST API 端点。
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_
import uuid
import time
import os
from flowpilot.audit.logger import AuditLogger

from flowpilot.core.db import get_db as db_get_db
from flowpilot.core.models import (
    Host,
    HostService,
    JumpConfig,
    Service,
    PolicyRule,
    LLMConfig,
    LLMProvider,
    AuditSession,
    AuditToolCall,
    Tag,
)

logger = logging.getLogger(__name__)

# ========== 依赖注入 ==========

# 直接使用 db.py 中的 get_db 函数
get_db = db_get_db


# ========== Pydantic 模型 ==========


class HostCreate(BaseModel):
    """创建主机请求."""
    name: str = Field(..., description="主机别名")
    addr: str = Field(..., description="主机地址")
    user: str = Field(..., description="SSH 用户名")
    port: int = Field(22, description="SSH 端口")
    env: str = Field("dev", description="环境: dev/staging/prod")
    description: str = Field("", description="备注")
    group: str = Field("default", description="分组")
    jump: str | None = Field(None, description="跳板机别名")
    ssh_key: str | None = Field(None, description="SSH 密钥路径")
    tags: list[str] = Field(default_factory=list, description="标签列表")


class HostUpdate(BaseModel):
    """更新主机请求."""
    addr: str | None = None
    user: str | None = None
    port: int | None = None
    env: str | None = None
    description: str | None = None
    group: str | None = None
    jump: str | None = None
    ssh_key: str | None = None
    tags: list[str] | None = None


class HostResponse(BaseModel):
    """主机响应."""
    id: int
    name: str
    addr: str
    user: str
    port: int
    env: str
    description: str
    group: str
    jump: str | None
    ssh_key: str | None
    tags: list[str]

    class Config:
        from_attributes = True


class JumpCreate(BaseModel):
    """创建跳板机请求."""
    name: str
    addr: str
    user: str
    port: int = 22


class JumpResponse(BaseModel):
    """跳板机响应."""
    id: int
    name: str
    addr: str
    user: str
    port: int

    class Config:
        from_attributes = True


class HostServiceCreate(BaseModel):
    """创建主机服务请求."""
    name: str = Field(..., description="服务名称（用户友好名，如'后端服务'）")
    service_name: str = Field(..., description="服务标识（如 ir_web.service）")
    service_type: str = Field("systemd", description="服务类型: systemd, docker, pm2")
    description: str = Field("", description="服务描述")


class HostServiceUpdate(BaseModel):
    """更新主机服务请求."""
    name: str | None = None
    service_name: str | None = None
    service_type: str | None = None
    description: str | None = None


class HostServiceResponse(BaseModel):
    """主机服务响应."""
    id: int
    host_id: int
    host_name: str  # 额外返回主机名
    name: str
    service_name: str
    service_type: str
    description: str

    class Config:
        from_attributes = True


class ServiceCreate(BaseModel):
    """创建服务请求."""
    name: str
    description: str = ""
    config_json: dict = Field(default_factory=dict)


class ServiceResponse(BaseModel):
    """服务响应."""
    id: int
    name: str
    description: str
    config_json: dict

    class Config:
        from_attributes = True


class PolicyCreate(BaseModel):
    """创建策略请求."""
    name: str
    condition: dict
    effect: str = "require_confirm"
    message: str = ""


class PolicyResponse(BaseModel):
    """策略响应."""
    id: int
    name: str
    condition: dict
    effect: str
    message: str

    class Config:
        from_attributes = True


class AuditSessionResponse(BaseModel):
    """审计会话响应."""
    session_id: str
    timestamp: str
    user: str
    input: str
    status: str
    provider: str | None
    total_duration_sec: float | None

    class Config:
        from_attributes = True


# ========== Router ==========

rest_router = APIRouter(prefix="/api", tags=["REST API"])


# ========== Hosts ==========


@rest_router.get("/hosts")
async def list_hosts(
    env: str | None = None,
    group: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
) -> list[HostResponse]:
    """获取主机列表."""
    query = db.query(Host)
    if env:
        query = query.filter(Host.env == env)
    if group:
        query = query.filter(Host.group == group)
    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                Host.name.ilike(search),
                Host.addr.ilike(search),
                Host.description.ilike(search),
            )
        )
    
    hosts = query.all()
    return [
        HostResponse(
            id=h.id,
            name=h.name,
            addr=h.addr,
            user=h.user,
            port=h.port,
            env=h.env,
            description=h.description,
            group=h.group,
            jump=h.jump,
            ssh_key=h.ssh_key,
            tags=[t.name for t in h.tags],
        )
        for h in hosts
    ]


@rest_router.get("/hosts/{name}")
async def get_host(name: str, db: Session = Depends(get_db)) -> HostResponse:
    """获取单个主机."""
    host = db.query(Host).filter(Host.name == name).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"主机 '{name}' 不存在")
    return HostResponse(
        id=host.id,
        name=host.name,
        addr=host.addr,
        user=host.user,
        port=host.port,
        env=host.env,
        description=host.description,
        group=host.group,
        jump=host.jump,
        ssh_key=host.ssh_key,
        tags=[t.name for t in host.tags],
    )


@rest_router.post("/hosts")
async def create_host(data: HostCreate, db: Session = Depends(get_db)) -> HostResponse:
    """创建主机."""
    # 检查是否已存在
    existing = db.query(Host).filter(Host.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"主机 '{data.name}' 已存在")
    
    # 处理标签
    tags = []
    for tag_name in data.tags:
        tag = db.query(Tag).filter(Tag.name == tag_name).first()
        if not tag:
            tag = Tag(name=tag_name)
            db.add(tag)
        tags.append(tag)
    
    host = Host(
        name=data.name,
        addr=data.addr,
        user=data.user,
        port=data.port,
        env=data.env,
        description=data.description,
        group=data.group,
        jump=data.jump,
        ssh_key=data.ssh_key,
        tags=tags,
    )
    db.add(host)
    db.commit()
    db.refresh(host)

    # 审计
    AuditLogger().create_session(
        session_id=f"api_{int(time.time())}_{uuid.uuid4().hex[:8]}",
        user_input=f"API: 创建主机 {data.name} ({data.addr})",
        input_mode="api"
    )
    
    return HostResponse(
        id=host.id,
        name=host.name,
        addr=host.addr,
        user=host.user,
        port=host.port,
        env=host.env,
        description=host.description,
        group=host.group,
        jump=host.jump,
        ssh_key=host.ssh_key,
        tags=[t.name for t in host.tags],
    )


@rest_router.put("/hosts/{name}")
async def update_host(
    name: str, data: HostUpdate, db: Session = Depends(get_db)
) -> HostResponse:
    """更新主机."""
    host = db.query(Host).filter(Host.name == name).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"主机 '{name}' 不存在")
    
    # 更新字段
    if data.addr is not None:
        host.addr = data.addr
    if data.user is not None:
        host.user = data.user
    if data.port is not None:
        host.port = data.port
    if data.env is not None:
        host.env = data.env
    if data.description is not None:
        host.description = data.description
    if data.group is not None:
        host.group = data.group
    if data.jump is not None:
        host.jump = data.jump
    if data.ssh_key is not None:
        host.ssh_key = data.ssh_key
    if data.tags is not None:
        tags = []
        for tag_name in data.tags:
            tag = db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.add(tag)
            tags.append(tag)
        host.tags = tags
    
    db.commit()
    db.refresh(host)

    # 审计
    AuditLogger().create_session(
        session_id=f"api_{int(time.time())}_{uuid.uuid4().hex[:8]}",
        user_input=f"API: 更新主机 {name}",
        input_mode="api"
    )
    
    return HostResponse(
        id=host.id,
        name=host.name,
        addr=host.addr,
        user=host.user,
        port=host.port,
        env=host.env,
        description=host.description,
        group=host.group,
        jump=host.jump,
        ssh_key=host.ssh_key,
        tags=[t.name for t in host.tags],
    )


@rest_router.delete("/hosts/{name}")
async def delete_host(name: str, db: Session = Depends(get_db)) -> dict[str, str]:
    """删除主机."""
    host = db.query(Host).filter(Host.name == name).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"主机 '{name}' 不存在")
    
    db.delete(host)
    db.commit()

    # 审计
    AuditLogger().create_session(
        session_id=f"api_{int(time.time())}_{uuid.uuid4().hex[:8]}",
        user_input=f"API: 删除主机 {name}",
        input_mode="api"
    )
    return {"message": f"已删除主机 '{name}'"}


# ========== Host Services (主机服务) ==========


@rest_router.get("/host-services")
async def list_all_host_services(
    host_name: str | None = None,
    service_type: str | None = None,
    db: Session = Depends(get_db),
) -> list[HostServiceResponse]:
    """获取所有主机服务列表（支持过滤）."""
    query = db.query(HostService).join(Host)
    if host_name:
        query = query.filter(Host.name == host_name)
    if service_type:
        query = query.filter(HostService.service_type == service_type)
    
    services = query.all()
    return [
        HostServiceResponse(
            id=s.id,
            host_id=s.host_id,
            host_name=s.host.name,
            name=s.name,
            service_name=s.service_name,
            service_type=s.service_type,
            description=s.description,
        )
        for s in services
    ]


@rest_router.get("/hosts/{host_name}/services")
async def list_host_services(
    host_name: str, db: Session = Depends(get_db)
) -> list[HostServiceResponse]:
    """获取指定主机的服务列表."""
    host = db.query(Host).filter(Host.name == host_name).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"主机 '{host_name}' 不存在")
    
    return [
        HostServiceResponse(
            id=s.id,
            host_id=s.host_id,
            host_name=host.name,
            name=s.name,
            service_name=s.service_name,
            service_type=s.service_type,
            description=s.description,
        )
        for s in host.host_services
    ]


@rest_router.post("/hosts/{host_name}/services")
async def create_host_service(
    host_name: str, data: HostServiceCreate, db: Session = Depends(get_db)
) -> HostServiceResponse:
    """为主机添加服务."""
    host = db.query(Host).filter(Host.name == host_name).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"主机 '{host_name}' 不存在")
    
    # 检查是否已存在同名服务
    existing = db.query(HostService).filter(
        HostService.host_id == host.id,
        HostService.name == data.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"主机 '{host_name}' 已存在名为 '{data.name}' 的服务"
        )
    
    service = HostService(
        host_id=host.id,
        name=data.name,
        service_name=data.service_name,
        service_type=data.service_type,
        description=data.description,
    )
    db.add(service)
    db.commit()
    db.refresh(service)

    # 审计
    AuditLogger().create_session(
        session_id=f"api_{int(time.time())}_{uuid.uuid4().hex[:8]}",
        user_input=f"API: 创建主机服务 {host_name} -> {data.name} ({data.service_name})",
        input_mode="api"
    )
    
    return HostServiceResponse(
        id=service.id,
        host_id=service.host_id,
        host_name=host.name,
        name=service.name,
        service_name=service.service_name,
        service_type=service.service_type,
        description=service.description,
    )


@rest_router.put("/hosts/{host_name}/services/{service_id}")
async def update_host_service(
    host_name: str,
    service_id: int,
    data: HostServiceUpdate,
    db: Session = Depends(get_db),
) -> HostServiceResponse:
    """更新主机服务."""
    host = db.query(Host).filter(Host.name == host_name).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"主机 '{host_name}' 不存在")
    
    service = db.query(HostService).filter(
        HostService.id == service_id,
        HostService.host_id == host.id
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail=f"服务 ID {service_id} 不存在")
    
    if data.name is not None:
        service.name = data.name
    if data.service_name is not None:
        service.service_name = data.service_name
    if data.service_type is not None:
        service.service_type = data.service_type
    if data.description is not None:
        service.description = data.description
    
    db.commit()
    db.refresh(service)

    # 审计
    AuditLogger().create_session(
        session_id=f"api_{int(time.time())}_{uuid.uuid4().hex[:8]}",
        user_input=f"API: 更新主机服务 {host_name} -> {service.name}",
        input_mode="api"
    )
    
    return HostServiceResponse(
        id=service.id,
        host_id=service.host_id,
        host_name=host.name,
        name=service.name,
        service_name=service.service_name,
        service_type=service.service_type,
        description=service.description,
    )


@rest_router.delete("/hosts/{host_name}/services/{service_id}")
async def delete_host_service(
    host_name: str, service_id: int, db: Session = Depends(get_db)
) -> dict[str, str]:
    """删除主机服务."""
    host = db.query(Host).filter(Host.name == host_name).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"主机 '{host_name}' 不存在")
    
    service = db.query(HostService).filter(
        HostService.id == service_id,
        HostService.host_id == host.id
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail=f"服务 ID {service_id} 不存在")
    
    service_name = service.name
    db.delete(service)
    db.commit()

    # 审计
    AuditLogger().create_session(
        session_id=f"api_{int(time.time())}_{uuid.uuid4().hex[:8]}",
        user_input=f"API: 删除主机服务 {host_name} -> {service_name}",
        input_mode="api"
    )

    return {"message": f"已删除主机 '{host_name}' 的服务 '{service_name}'"}


# ========== Jumps ==========


@rest_router.get("/jumps")
async def list_jumps(db: Session = Depends(get_db)) -> list[JumpResponse]:
    """获取跳板机列表."""
    jumps = db.query(JumpConfig).all()
    return [JumpResponse.model_validate(j) for j in jumps]


@rest_router.get("/jumps/{name}")
async def get_jump(name: str, db: Session = Depends(get_db)) -> JumpResponse:
    """获取单个跳板机."""
    jump = db.query(JumpConfig).filter(JumpConfig.name == name).first()
    if not jump:
        raise HTTPException(status_code=404, detail=f"跳板机 '{name}' 不存在")
    return JumpResponse.model_validate(jump)


@rest_router.post("/jumps")
async def create_jump(data: JumpCreate, db: Session = Depends(get_db)) -> JumpResponse:
    """创建跳板机."""
    existing = db.query(JumpConfig).filter(JumpConfig.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"跳板机 '{data.name}' 已存在")
    
    jump = JumpConfig(**data.model_dump())
    db.add(jump)
    db.commit()
    db.refresh(jump)
    return JumpResponse.model_validate(jump)


@rest_router.delete("/jumps/{name}")
async def delete_jump(name: str, db: Session = Depends(get_db)) -> dict[str, str]:
    """删除跳板机."""
    jump = db.query(JumpConfig).filter(JumpConfig.name == name).first()
    if not jump:
        raise HTTPException(status_code=404, detail=f"跳板机 '{name}' 不存在")
    
    db.delete(jump)
    db.commit()
    return {"message": f"已删除跳板机 '{name}'"}


# ========== Services ==========


@rest_router.get("/services")
async def list_services(db: Session = Depends(get_db)) -> list[ServiceResponse]:
    """获取服务列表."""
    services = db.query(Service).all()
    return [ServiceResponse.model_validate(s) for s in services]


@rest_router.get("/services/{name}")
async def get_service(name: str, db: Session = Depends(get_db)) -> ServiceResponse:
    """获取单个服务."""
    service = db.query(Service).filter(Service.name == name).first()
    if not service:
        raise HTTPException(status_code=404, detail=f"服务 '{name}' 不存在")
    return ServiceResponse.model_validate(service)


@rest_router.post("/services")
async def create_service(
    data: ServiceCreate, db: Session = Depends(get_db)
) -> ServiceResponse:
    """创建服务."""
    existing = db.query(Service).filter(Service.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"服务 '{data.name}' 已存在")
    
    service = Service(**data.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)
    return ServiceResponse.model_validate(service)


@rest_router.delete("/services/{name}")
async def delete_service(name: str, db: Session = Depends(get_db)) -> dict[str, str]:
    """删除服务."""
    service = db.query(Service).filter(Service.name == name).first()
    if not service:
        raise HTTPException(status_code=404, detail=f"服务 '{name}' 不存在")
    
    db.delete(service)
    db.commit()
    return {"message": f"已删除服务 '{name}'"}


# ========== Policies ==========


@rest_router.get("/policies")
async def list_policies(db: Session = Depends(get_db)) -> list[PolicyResponse]:
    """获取策略列表."""
    policies = db.query(PolicyRule).all()
    return [PolicyResponse.model_validate(p) for p in policies]


@rest_router.get("/policies/{name}")
async def get_policy(name: str, db: Session = Depends(get_db)) -> PolicyResponse:
    """获取单个策略."""
    policy = db.query(PolicyRule).filter(PolicyRule.name == name).first()
    if not policy:
        raise HTTPException(status_code=404, detail=f"策略 '{name}' 不存在")
    return PolicyResponse.model_validate(policy)


@rest_router.post("/policies")
async def create_policy(
    data: PolicyCreate, db: Session = Depends(get_db)
) -> PolicyResponse:
    """创建策略."""
    existing = db.query(PolicyRule).filter(PolicyRule.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"策略 '{data.name}' 已存在")
    
    policy = PolicyRule(**data.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return PolicyResponse.model_validate(policy)


@rest_router.delete("/policies/{name}")
async def delete_policy(name: str, db: Session = Depends(get_db)) -> dict[str, str]:
    """删除策略."""
    policy = db.query(PolicyRule).filter(PolicyRule.name == name).first()
    if not policy:
        raise HTTPException(status_code=404, detail=f"策略 '{name}' 不存在")
    
    db.delete(policy)
    db.commit()
    return {"message": f"已删除策略 '{name}'"}


# ========== Audit Sessions ==========


@rest_router.get("/audit/sessions")
async def list_audit_sessions(
    limit: int = 20,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[AuditSessionResponse]:
    """获取审计会话列表."""
    query = db.query(AuditSession).order_by(AuditSession.timestamp.desc())
    if status:
        query = query.filter(AuditSession.status == status)
    
    sessions = query.limit(limit).all()
    return [
        AuditSessionResponse(
            session_id=s.session_id,
            timestamp=s.timestamp.isoformat() if s.timestamp else "",
            user=s.user,
            input=s.input,
            status=s.status,
            provider=s.provider,
            total_duration_sec=s.total_duration_sec,
        )
        for s in sessions
    ]


@rest_router.get("/audit/sessions/{session_id}")
async def get_audit_session(
    session_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """获取审计会话详情."""
    session = db.query(AuditSession).filter(
        AuditSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")
    
    return {
        "session_id": session.session_id,
        "timestamp": session.timestamp.isoformat() if session.timestamp else None,
        "user": session.user,
        "hostname": session.hostname,
        "input": session.input,
        "final_output": session.final_output,
        "agent_reasoning": session.agent_reasoning,
        "provider": session.provider,
        "status": session.status,
        "token_usage": session.token_usage,
        "total_duration_sec": session.total_duration_sec,
        "cost_usd": session.cost_usd,
        "tool_calls": [
            {
                "call_id": tc.call_id,
                "tool_name": tc.tool_name,
                "tool_args": tc.tool_args,
                "status": tc.status,
                "duration_sec": tc.duration_sec,
                "stdout_summary": tc.stdout_summary,
            }
            for tc in session.tool_calls
        ],
    }


# ========== Dashboard Stats ==========


@rest_router.get("/stats")
async def get_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
    """获取仪表盘统计数据."""
    return {
        "hosts_count": db.query(Host).count(),
        "jumps_count": db.query(JumpConfig).count(),
        "services_count": db.query(Service).count(),
        "policies_count": db.query(PolicyRule).count(),
        "sessions_count": db.query(AuditSession).count(),
        "recent_sessions": db.query(AuditSession).order_by(
            AuditSession.timestamp.desc()
        ).limit(5).count(),
    }
