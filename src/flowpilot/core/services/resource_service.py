
from flowpilot.core.models import JumpConfig, PolicyRule, Service
from flowpilot.core.repositories.others import JumpRepository, PolicyRepository, ServiceRepository
from flowpilot.core.schemas import JumpCreate, PolicyCreate, ServiceCreate
from flowpilot.core.services.base import BaseService


class ResourceService(BaseService):
    """通用资源服务 (Jumps, Services, Policies)."""

    def __init__(self, db):
        super().__init__(db)
        self.jump_repo = JumpRepository(db)
        self.service_repo = ServiceRepository(db)
        self.policy_repo = PolicyRepository(db)

    # ========== JumpConfig ==========

    def count_jumps(self) -> int:
        return self.jump_repo.count()

    def list_jumps(self) -> list[JumpConfig]:
        return self.jump_repo.list()

    def get_jump(self, name: str) -> JumpConfig:
        return self.jump_repo.get_by_name(name)

    def create_jump(self, data: JumpCreate) -> JumpConfig:
        if self.jump_repo.get_by_name(data.name):
            raise ValueError(f"跳板机 '{data.name}' 已存在")
        jump = self.jump_repo.create(data.model_dump())
        return jump

    def delete_jump(self, name: str) -> None:
        jump = self.jump_repo.get_by_name(name)
        if not jump:
            raise ValueError(f"跳板机 '{name}' 不存在")
        self.jump_repo.delete(jump.id)

    # ========== Service (Global) ==========

    def count_services(self) -> int:
        return self.service_repo.count()

    def list_services(self) -> list[Service]:
        return self.service_repo.list()

    def get_service(self, name: str) -> Service:
        return self.service_repo.get_by_name(name)

    def create_service(self, data: ServiceCreate) -> Service:
        if self.service_repo.get_by_name(data.name):
            raise ValueError(f"服务 '{data.name}' 已存在")
        service = self.service_repo.create(data.model_dump())
        return service

    def delete_service(self, name: str) -> None:
        service = self.service_repo.get_by_name(name)
        if not service:
            raise ValueError(f"服务 '{name}' 不存在")
        self.service_repo.delete(service.id)

    # ========== Policy ==========

    def count_policies(self) -> int:
        return self.policy_repo.count()

    def list_policies(self) -> list[PolicyRule]:
        return self.policy_repo.list()

    def get_policy(self, name: str) -> PolicyRule:
        return self.policy_repo.get_by_name(name)

    def create_policy(self, data: PolicyCreate) -> PolicyRule:
        if self.policy_repo.get_by_name(data.name):
             raise ValueError(f"策略 '{data.name}' 已存在")
        policy = self.policy_repo.create(data.model_dump())
        return policy

    def delete_policy(self, name: str) -> None:
        policy = self.policy_repo.get_by_name(name)
        if not policy:
            raise ValueError(f"策略 '{name}' 不存在")
        self.policy_repo.delete(policy.id)
