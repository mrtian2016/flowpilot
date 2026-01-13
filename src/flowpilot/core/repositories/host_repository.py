
from sqlalchemy import or_

from flowpilot.core.models import Host, Tag
from flowpilot.core.repositories.base import BaseRepository


class HostRepository(BaseRepository[Host]):
    """Host Repository."""

    def __init__(self, db):
        super().__init__(Host, db)

    def get_by_name(self, name: str) -> Host | None:
        """根据名称获取主机."""
        return self.get_by(name=name)

    def search(self, q: str) -> list[Host]:
        """搜索主机."""
        search = f"%{q}%"
        return self.db.query(Host).filter(
            or_(
                Host.name.ilike(search),
                Host.addr.ilike(search),
                Host.description.ilike(search),
            )
        ).all()

    def get_tag_by_name(self, name: str) -> Tag | None:
        """获取标签 (辅助方法)."""
        return self.db.query(Tag).filter(Tag.name == name).first()

    def create_tag(self, name: str) -> Tag:
        """创建标签 (辅助方法)."""
        tag = Tag(name=name)
        self.db.add(tag)
        # Flush to get ID, but let service commit
        self.db.flush()
        return tag
