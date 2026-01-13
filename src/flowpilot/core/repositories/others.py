
from flowpilot.core.models import AuditSession, HostService, JumpConfig, PolicyRule, Service
from flowpilot.core.repositories.base import BaseRepository


class JumpRepository(BaseRepository[JumpConfig]):
    """JumpConfig Repository."""
    def __init__(self, db):
        super().__init__(JumpConfig, db)

    def get_by_name(self, name: str) -> JumpConfig | None:
        return self.get_by(name=name)


class ServiceRepository(BaseRepository[Service]):
    """Service Repository (Generic Services)."""
    def __init__(self, db):
        super().__init__(Service, db)

    def get_by_name(self, name: str) -> Service | None:
        return self.get_by(name=name)


class HostServiceRepository(BaseRepository[HostService]):
    """HostService Repository (Services running on Hosts)."""
    def __init__(self, db):
        super().__init__(HostService, db)

    def get_by_host_and_name(self, host_id: int, name: str) -> HostService | None:
        return self.get_by(host_id=host_id, name=name)

    def search(self, q_host: str = None, q_service: str = None) -> list[HostService]:
        """搜索主机服务（支持模糊匹配）."""
        from sqlalchemy import or_

        from flowpilot.core.models import Host

        query = self.db.query(HostService).join(Host)

        if q_host:
            query = query.filter(
                or_(
                    Host.name.ilike(f"%{q_host}%"),
                    Host.description.ilike(f"%{q_host}%")
                )
            )

        if q_service:
            query = query.filter(
                or_(
                    HostService.name.ilike(f"%{q_service}%"),
                    HostService.service_name.ilike(f"%{q_service}%"),
                    HostService.description.ilike(f"%{q_service}%")
                )
            )

        return query.all()

    def list_with_filters(self, host_name: str = None, service_type: str = None) -> list[HostService]:
        """获取主机服务列表（支持过滤）."""
        from flowpilot.core.models import Host

        query = self.db.query(HostService).join(Host)
        if host_name:
            query = query.filter(Host.name == host_name)
        if service_type:
            query = query.filter(HostService.service_type == service_type)
        return query.all()


class PolicyRepository(BaseRepository[PolicyRule]):
    """PolicyRule Repository."""
    def __init__(self, db):
        super().__init__(PolicyRule, db)

    def get_by_name(self, name: str) -> PolicyRule | None:
        return self.get_by(name=name)


class AuditRepository(BaseRepository[AuditSession]):
    """AuditSession Repository."""
    def __init__(self, db):
        super().__init__(AuditSession, db)

    def get(self, session_id: str) -> AuditSession | None:
        """根据 session_id 获取审计会话（重写基类方法，因为主键是 session_id 不是 id）."""
        return self.db.query(AuditSession).filter(
            AuditSession.session_id == session_id
        ).first()

    def list_ordered(self, limit: int = 20, status: str = None) -> list[AuditSession]:
        """获取审计会话列表（按时间倒序）."""
        query = self.db.query(AuditSession)
        if status:
            query = query.filter(AuditSession.status == status)
        return query.order_by(AuditSession.timestamp.desc()).limit(limit).all()

    def get_recent(self, limit: int = 5) -> list[AuditSession]:
        """获取最近的审计会话."""
        return self.db.query(AuditSession).order_by(
            AuditSession.timestamp.desc()
        ).limit(limit).all()
