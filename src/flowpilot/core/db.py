"""数据库连接和会话管理."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# 数据库文件路径
DB_DIR = Path.home() / ".flowpilot"
DB_FILE = DB_DIR / "flowpilot.db"


class Base(DeclarativeBase):
    """SQLAlchemy Base class."""

    pass


# 延迟初始化的 engine 和 session
_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """获取数据库 engine（延迟初始化）."""
    global _engine
    if _engine is None:
        db_url = f"sqlite:///{DB_FILE}"
        _engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """获取 Session 工厂（延迟初始化）."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


class SessionLocal:
    """Session 上下文管理器，支持 with 语句."""

    def __init__(self) -> None:
        self._session: Session | None = None

    def __enter__(self) -> Session:
        factory = get_session_factory()
        self._session = factory()
        return self._session

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: object) -> None:
        if self._session:
            self._session.close()


def init_db() -> None:
    """初始化数据库表."""
    if not DB_DIR.exists():
        DB_DIR.mkdir(parents=True)

    # 创建所有表
    Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话.

    Yields:
        SQLAlchemy Session
    """
    with SessionLocal() as db:
        yield db


def reset_engine() -> None:
    """重置 engine（用于测试）."""
    global _engine, _SessionLocal
    if _engine:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def set_engine(engine: Engine) -> None:
    """设置自定义 engine（用于测试）."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
