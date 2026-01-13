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
from flowpilot.core.services import HostService, ResourceService, AuditService
from flowpilot.core.schemas import (
    HostCreate, HostUpdate, HostResponse,
    HostServiceCreate, HostServiceUpdate, HostServiceResponse,
    JumpCreate, JumpResponse,
    ServiceCreate, ServiceResponse,
    PolicyCreate, PolicyResponse,
    AuditSessionResponse
)

logger = logging.getLogger(__name__)

# ========== 依赖注入 ==========

# 直接使用 db.py 中的 get_db 函数
get_db = db_get_db

def get_host_service(db: Session = Depends(get_db)) -> HostService:
    return HostService(db)

def get_resource_service(db: Session = Depends(get_db)) -> ResourceService:
    return ResourceService(db)

def get_audit_service(db: Session = Depends(get_db)) -> AuditService:
    return AuditService(db)


# ========== Pydantic 模型 ==========


# ========== Pydantic 模型 (Moved to schemas.py) ==========



# ========== Router ==========

rest_router = APIRouter(prefix="/api", tags=["REST API"])


# ========== Hosts ==========


@rest_router.get("/hosts")
async def list_hosts(
    env: str | None = None,
    group: str | None = None,
    q: str | None = None,
    service: HostService = Depends(get_host_service),
) -> list[HostResponse]:
    """获取主机列表."""
    hosts = service.list(env=env, group=group, q=q)
    return [HostResponse.model_validate(h) for h in hosts]


@rest_router.get("/hosts/{name}")
async def get_host(name: str, service: HostService = Depends(get_host_service)) -> HostResponse:
    """获取单个主机."""
    host = service.get(name)
    if not host:
        raise HTTPException(status_code=404, detail=f"主机 '{name}' 不存在")
    return HostResponse.model_validate(host)


@rest_router.post("/hosts")
async def create_host(data: HostCreate, service: HostService = Depends(get_host_service)) -> HostResponse:
    """创建主机."""
    try:
        host = service.create(data)
        return HostResponse.model_validate(host)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@rest_router.put("/hosts/{name}")
async def update_host(
    name: str, data: HostUpdate, service: HostService = Depends(get_host_service)
) -> HostResponse:
    """更新主机."""
    try:
        host = service.update(name, data)
        return HostResponse.model_validate(host)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@rest_router.delete("/hosts/{name}")
async def delete_host(name: str, service: HostService = Depends(get_host_service)) -> dict[str, str]:
    """删除主机."""
    try:
        service.delete(name)
        return {"message": f"已删除主机 '{name}'"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========== Host Services (主机服务) ==========


@rest_router.get("/host-services")
async def list_all_host_services(
    host_name: str | None = None,
    service_type: str | None = None,
    service: HostService = Depends(get_host_service),
) -> list[HostServiceResponse]:
    """获取所有主机服务列表（支持过滤）."""
    services = service.list_all_services(host_name=host_name, service_type=service_type)
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
    host_name: str, service: HostService = Depends(get_host_service)
) -> list[HostServiceResponse]:
    """获取指定主机的服务列表."""
    try:
        services = service.list_services(host_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    # We need host name for response, services have host relation loaded? 
    # Or services already associated.
    # The return type HostServiceResponse requires host_name.
    # host.host_services query automatically joins? 
    # Yes, SQLAlchemy lazy loading or we access s.host.name.
    # Service layer returns models.
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


@rest_router.post("/hosts/{host_name}/services")
async def create_host_service(
    host_name: str, data: HostServiceCreate, service: HostService = Depends(get_host_service)
) -> HostServiceResponse:
    """为主机添加服务."""
    try:
        s = service.create_service(host_name, data)
        return HostServiceResponse(
            id=s.id,
            host_id=s.host_id,
            host_name=s.host.name,
            name=s.name,
            service_name=s.service_name,
            service_type=s.service_type,
            description=s.description,
        )
    except ValueError as e:
        # Assuming duplicate or not found maps to 400 or 404. Service raises ValueError.
        # "not found" -> 404, "exists" -> 400.
        # Simple mapping:
        err_msg = str(e)
        if "不存在" in err_msg:
             raise HTTPException(status_code=404, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)


@rest_router.put("/hosts/{host_name}/services/{service_id}")
async def update_host_service(
    host_name: str,
    service_id: int,
    data: HostServiceUpdate,
    service: HostService = Depends(get_host_service),
) -> HostServiceResponse:
    """更新主机服务."""
    try:
        s = service.update_service(host_name, service_id, data)
        return HostServiceResponse(
            id=s.id,
            host_id=s.host_id,
            host_name=s.host.name,
            name=s.name,
            service_name=s.service_name,
            service_type=s.service_type,
            description=s.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@rest_router.delete("/hosts/{host_name}/services/{service_id}")
async def delete_host_service(
    host_name: str, service_id: int, service: HostService = Depends(get_host_service)
) -> dict[str, str]:
    """删除主机服务."""
    try:
        service_name = service.delete_service(host_name, service_id)
        return {"message": f"已删除主机 '{host_name}' 的服务 '{service_name}'"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========== Jumps ==========


@rest_router.get("/jumps")
async def list_jumps(service: ResourceService = Depends(get_resource_service)) -> list[JumpResponse]:
    """获取跳板机列表."""
    jumps = service.list_jumps()
    return [JumpResponse.model_validate(j) for j in jumps]


@rest_router.get("/jumps/{name}")
async def get_jump(name: str, service: ResourceService = Depends(get_resource_service)) -> JumpResponse:
    """获取单个跳板机."""
    jump = service.get_jump(name)
    if not jump:
        raise HTTPException(status_code=404, detail=f"跳板机 '{name}' 不存在")
    return JumpResponse.model_validate(jump)


@rest_router.post("/jumps")
async def create_jump(data: JumpCreate, service: ResourceService = Depends(get_resource_service)) -> JumpResponse:
    """创建跳板机."""
    try:
        jump = service.create_jump(data)
        return JumpResponse.model_validate(jump)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@rest_router.delete("/jumps/{name}")
async def delete_jump(name: str, service: ResourceService = Depends(get_resource_service)) -> dict[str, str]:
    """删除跳板机."""
    try:
        service.delete_jump(name)
        return {"message": f"已删除跳板机 '{name}'"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========== Services ==========


@rest_router.get("/services")
async def list_services(service: ResourceService = Depends(get_resource_service)) -> list[ServiceResponse]:
    """获取服务列表."""
    services = service.list_services()
    return [ServiceResponse.model_validate(s) for s in services]


@rest_router.get("/services/{name}")
async def get_service(name: str, service: ResourceService = Depends(get_resource_service)) -> ServiceResponse:
    """获取单个服务."""
    s = service.get_service(name)
    if not s:
        raise HTTPException(status_code=404, detail=f"服务 '{name}' 不存在")
    return ServiceResponse.model_validate(s)


@rest_router.post("/services")
async def create_service(
    data: ServiceCreate, service: ResourceService = Depends(get_resource_service)
) -> ServiceResponse:
    """创建服务."""
    try:
        s = service.create_service(data)
        return ServiceResponse.model_validate(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@rest_router.delete("/services/{name}")
async def delete_service(name: str, service: ResourceService = Depends(get_resource_service)) -> dict[str, str]:
    """删除服务."""
    try:
        service.delete_service(name)
        return {"message": f"已删除服务 '{name}'"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========== Policies ==========


@rest_router.get("/policies")
async def list_policies(service: ResourceService = Depends(get_resource_service)) -> list[PolicyResponse]:
    """获取策略列表."""
    policies = service.list_policies()
    return [PolicyResponse.model_validate(p) for p in policies]


@rest_router.get("/policies/{name}")
async def get_policy(name: str, service: ResourceService = Depends(get_resource_service)) -> PolicyResponse:
    """获取单个策略."""
    policy = service.get_policy(name)
    if not policy:
        raise HTTPException(status_code=404, detail=f"策略 '{name}' 不存在")
    return PolicyResponse.model_validate(policy)


@rest_router.post("/policies")
async def create_policy(
    data: PolicyCreate, service: ResourceService = Depends(get_resource_service)
) -> PolicyResponse:
    """创建策略."""
    try:
        policy = service.create_policy(data)
        return PolicyResponse.model_validate(policy)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@rest_router.delete("/policies/{name}")
async def delete_policy(name: str, service: ResourceService = Depends(get_resource_service)) -> dict[str, str]:
    """删除策略."""
    try:
        service.delete_policy(name)
        return {"message": f"已删除策略 '{name}'"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========== Audit Sessions ==========


@rest_router.get("/audit/sessions")
async def list_audit_sessions(
    limit: int = 20,
    status: str | None = None,
    service: AuditService = Depends(get_audit_service),
) -> list[AuditSessionResponse]:
    """获取审计会话列表."""
    sessions = service.list_sessions(limit=limit, status=status)
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
    session_id: str, service: AuditService = Depends(get_audit_service)
) -> dict[str, Any]:
    """获取审计会话详情."""
    session = service.get_session(session_id)
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
async def get_stats(
    host_service: HostService = Depends(get_host_service),
    resource_service: ResourceService = Depends(get_resource_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> dict[str, Any]:
    """获取仪表盘统计数据."""
    return {
        "hosts_count": host_service.count(),
        "jumps_count": resource_service.count_jumps(),
        "services_count": resource_service.count_services(),
        "policies_count": resource_service.count_policies(),
        "sessions_count": audit_service.count_sessions(),
        "recent_sessions": audit_service.count_recent_sessions(limit=5),
    }
