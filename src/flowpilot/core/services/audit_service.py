
from flowpilot.core.models import AuditSession
from flowpilot.core.repositories.others import AuditRepository
from flowpilot.core.services.base import BaseService


class AuditService(BaseService):
    """Audit Service for retrieving audit logs."""

    def __init__(self, db):
        super().__init__(db)
        self.repo = AuditRepository(db)

    def count_sessions(self) -> int:
        return self.repo.count()

    def count_recent_sessions(self, limit: int = 5) -> int:
        """获取最近会话数量（用于 stats 接口）."""
        return len(self.repo.get_recent(limit=limit))

    def list_sessions(self, limit: int = 20, status: str = None) -> list[AuditSession]:
        """List audit sessions."""
        return self.repo.list_ordered(limit=limit, status=status)

    def get_session(self, session_id: str) -> AuditSession | None:
        return self.repo.get(session_id)
