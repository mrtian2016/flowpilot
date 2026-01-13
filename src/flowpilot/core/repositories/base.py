"""Repository 基类."""

from typing import Any, Generic, TypeVar

from sqlalchemy.orm import Session

from flowpilot.core.db import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """SQLAlchemy Repository 基类."""

    def __init__(self, model: type[ModelType], db: Session):
        """初始化 Repository.

        Args:
            model: SQLAlchemy 模型类
            db: 数据库会话
        """
        self.model = model
        self.db = db

    def get(self, id: Any) -> ModelType | None:
        """根据 ID 获取记录."""
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_by(self, **kwargs) -> ModelType | None:
        """根据条件获取单条记录."""
        return self.db.query(self.model).filter_by(**kwargs).first()

    def list(self, skip: int = 0, limit: int = 100, **kwargs) -> list[ModelType]:
        """获取列表, 支持简单的 filter_by 过滤."""
        query = self.db.query(self.model)
        if kwargs:
            query = query.filter_by(**kwargs)
        return query.offset(skip).limit(limit).all()

    def count(self, **kwargs) -> int:
        """获取数量."""
        query = self.db.query(self.model)
        if kwargs:
            query = query.filter_by(**kwargs)
        return query.count()

    def create(self, obj_in: dict | ModelType) -> ModelType:
        """创建记录."""
        if isinstance(obj_in, dict):
            db_obj = self.model(**obj_in)
        else:
            db_obj = obj_in

        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: ModelType, obj_in: dict | Any) -> ModelType:
        """更新记录."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)

        for field in update_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])

        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, id: int) -> ModelType | None:
        """删除记录."""
        obj = self.db.get(self.model, id)
        if obj:
            self.db.delete(obj)
            self.db.commit()
        return obj
