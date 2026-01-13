from sqlalchemy.orm import Session


class BaseService:
    """Service 基类."""

    def __init__(self, db: Session):
        self.db = db
