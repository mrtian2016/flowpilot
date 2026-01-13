import builtins
import time
import uuid

from flowpilot.audit.logger import AuditLogger
from flowpilot.core.models import Host
from flowpilot.core.models import HostService as HostServiceModel
from flowpilot.core.repositories.host_repository import HostRepository
from flowpilot.core.repositories.others import HostServiceRepository
from flowpilot.core.schemas import HostCreate, HostServiceCreate, HostServiceUpdate, HostUpdate
from flowpilot.core.services.base import BaseService


class HostService(BaseService):
    """主机管理服务."""

    def __init__(self, db):
        super().__init__(db)
        self.repo = HostRepository(db)
        self.service_repo = HostServiceRepository(db) # Note: repo expects Model class, but init calls super using ServiceRepo(HostService, db).
        # Wait, HostServiceRepository init was: super().__init__(HostService, db).
        # So I need to verify HostServiceRepository definition too if I change import there.
        # But here I am only changing import in service file.
        # So I need to update usages in this file.


    def count(self, **kwargs) -> int:
        return self.repo.count(**kwargs)

    def list(self, env: str = None, group: str = None, q: str = None) -> list[Host]:
        """获取主机列表."""
        if q:
            return self.repo.search(q)

        filters = {}
        if env:
            filters["env"] = env
        if group:
            filters["group"] = group
        return self.repo.list(**filters)

    def get(self, name: str) -> Host:
        """获取单个主机."""
        return self.repo.get_by_name(name)

    def create(self, data: HostCreate) -> Host:
        """创建主机."""
        if self.repo.get_by_name(data.name):
            raise ValueError(f"主机 '{data.name}' 已存在")

        # 处理标签
        tags = []
        for tag_name in data.tags:
            tag = self.repo.get_tag_by_name(tag_name)
            if not tag:
                tag = self.repo.create_tag(tag_name)
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
        self.repo.create(host)

        # 审计
        self._audit(f"API: 创建主机 {data.name} ({data.addr})")

        return host

    def update(self, name: str, data: HostUpdate) -> Host:
        """更新主机."""
        host = self.repo.get_by_name(name)
        if not host:
            raise ValueError(f"主机 '{name}' 不存在")

        # 处理特殊字段 Tags
        if data.tags is not None:
            tags = []
            for tag_name in data.tags:
                tag = self.repo.get_tag_by_name(tag_name)
                if not tag:
                    tag = self.repo.create_tag(tag_name)
                tags.append(tag)
            host.tags = tags
            # Remove tags from data to avoid double update or error
            # But BaseRepo update uses setattr, so we should exclude it from obj_in if we pass dict

        # Use simple update for other fields
        # Exclude 'tags' from default update loop if handled above?
        # Pydantic dict() has exclude.
        update_data = data.model_dump(exclude_unset=True, exclude={"tags"})
        self.repo.update(host, update_data)

        # 审计
        self._audit(f"API: 更新主机 {name}")

        return host

    def delete(self, name: str) -> None:
        """删除主机."""
        host = self.repo.get_by_name(name)
        if not host:
            raise ValueError(f"主机 '{name}' 不存在")

        self.repo.delete(host.id)

        # 审计
        self._audit(f"API: 删除主机 {name}")

    # ========== Host Services ==========

    def search_services(self, q_host: str = None, q_service: str = None) -> builtins.list[HostServiceModel]:
        """搜索主机服务 (支持模糊匹配)."""
        return self.service_repo.search(q_host=q_host, q_service=q_service)

    def list_all_services(self, host_name: str = None, service_type: str = None) -> builtins.list[HostServiceModel]:
        """获取所有主机服务列表."""
        return self.service_repo.list_with_filters(host_name=host_name, service_type=service_type)

    def list_services(self, host_name: str) -> builtins.list[HostServiceModel]:
        """获取主机服务列表."""
        host = self.repo.get_by_name(host_name)
        if not host:
            raise ValueError(f"主机 '{host_name}' 不存在")
        return host.host_services

    def create_service(self, host_name: str, data: HostServiceCreate) -> HostServiceModel:
        """创建主机服务."""
        host = self.repo.get_by_name(host_name)
        if not host:
            raise ValueError(f"主机 '{host_name}' 不存在")

        if self.service_repo.get_by_host_and_name(host.id, data.name):
            raise ValueError(f"主机 '{host_name}' 已存在名为 '{data.name}' 的服务")

        service = HostServiceModel(
            host_id=host.id,
            name=data.name,
            service_name=data.service_name,
            service_type=data.service_type,
            description=data.description,
        )
        self.service_repo.create(service)

        # 审计
        self._audit(f"API: 创建主机服务 {host_name} -> {data.name} ({data.service_name})")
        return service

    def update_service(self, host_name: str, service_id: int, data: HostServiceUpdate) -> HostServiceModel:
        """更新主机服务."""
        host = self.repo.get_by_name(host_name)
        if not host:
            raise ValueError(f"主机 '{host_name}' 不存在")

        service = self.service_repo.get(service_id)
        if not service or service.host_id != host.id:
            # Check host_id match to ensure security
            raise ValueError(f"服务 ID {service_id} 不属于主机 {host_name}")

        self.service_repo.update(service, data)

        # 审计
        self._audit(f"API: 更新主机服务 {host_name} -> {service.name}")
        return service

    def delete_service(self, host_name: str, service_id: int) -> str:
        """删除主机服务，返回被删除的服务名称."""
        host = self.repo.get_by_name(host_name)
        if not host:
            raise ValueError(f"主机 '{host_name}' 不存在")

        service = self.service_repo.get(service_id)
        # Check ownership
        if not service or service.host_id != host.id:
             raise ValueError(f"服务 ID {service_id} 不属于主机 {host_name}")

        service_name = service.name
        self.service_repo.delete(service.id)

        # 审计
        self._audit(f"API: 删除主机服务 {host_name} -> {service_name}")

        return service_name

    def _audit(self, message: str):
        """记录审计日志."""
        try:
            AuditLogger().create_session(
                session_id=f"api_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                user_input=message,
                input_mode="api"
            )
        except Exception:
            # Audit failure should not block main logic
            pass
