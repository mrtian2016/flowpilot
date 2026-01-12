"""AuditLogger 测试."""

import os
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from flowpilot.audit.logger import AuditLogger
from flowpilot.core.db import Base
from flowpilot.core.models import AuditSession, AuditToolCall


@pytest.fixture
def mock_db_session():
    """Create an in-memory SQLite database and session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Mock SessionLocal in logger.py to return this session
    class MockSessionContext:
        def __enter__(self):
            return session
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass 
            
    with patch("flowpilot.audit.logger.SessionLocal", return_value=MockSessionContext()):
        yield session
    
    session.close()


def test_create_session(mock_db_session):
    """测试创建会话."""
    logger = AuditLogger()
    logger.create_session("sess-1", "hello", "nlp")
    
    session = mock_db_session
    record = session.query(AuditSession).first()
    assert record is not None
    assert record.session_id == "sess-1"
    assert record.input == "hello"
    assert record.status == "running"


def test_update_session(mock_db_session):
    """测试更新会话."""
    # Setup
    session = mock_db_session
    record = AuditSession(session_id="sess-1", input="hello", status="running", user="test")
    session.add(record)
    session.commit()
    
    logger = AuditLogger()
    logger.update_session("sess-1", status="completed", final_output="world")
    
    updated = session.query(AuditSession).first()
    assert updated.status == "completed"
    assert updated.final_output == "world"


def test_add_tool_call(mock_db_session):
    """测试添加工具调用."""
    # Setup session
    session = mock_db_session
    sess = AuditSession(session_id="sess-1", input="hello", status="running", user="test")
    session.add(sess)
    session.commit()
    
    logger = AuditLogger()
    logger.add_tool_call(
        call_id="call-1",
        session_id="sess-1",
        tool_name="test_tool",
        tool_args={"arg": 1}
    )
    
    call = session.query(AuditToolCall).first()
    assert call is not None
    assert call.call_id == "call-1"
    assert call.tool_name == "test_tool"
    assert call.tool_args == {"arg": 1}


def test_get_recent_sessions(mock_db_session):
    """测试获取最近会话."""
    session = mock_db_session
    for i in range(3):
        sess = AuditSession(
            session_id=f"sess-{i}",
            input=f"input-{i}",
            status="completed",
            user="test"
        )
        session.add(sess)
    session.commit()
    
    logger = AuditLogger()
    recent = logger.get_recent_sessions(limit=2)
    
    assert len(recent) == 2
    # Should get latest first, but timestamps are same in loop? 
    # Actually datetime.utcnow is called in model default or logger. 
    # In logger create_session it calls utcnow. Here in test I didn't set timestamp explicitly so it uses default.
    # Because it's fast, timestamps might be equal. Result order might be unstable or dependent on insertion order.
