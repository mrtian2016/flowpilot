import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from flowpilot.core.db import Base
from flowpilot.core.services.host_service import HostService
from flowpilot.core.schemas import HostCreate, HostUpdate

# In-memory DB for testing
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_host_service_create(db_session):
    service = HostService(db_session)
    data = HostCreate(
        name="test-host",
        addr="1.2.3.4",
        user="root",
        env="dev",
        tags=["web", "api"]
    )
    host = service.create(data)
    
    assert host.id is not None
    assert host.name == "test-host"
    assert len(host.tags) == 2
    assert host.tags[0].name == "web"

    # Verify duplicates
    with pytest.raises(ValueError):
        service.create(data)

def test_host_service_update(db_session):
    service = HostService(db_session)
    data = HostCreate(name="test-host", addr="1.2.3.4", user="root", env="dev")
    service.create(data)
    
    update_data = HostUpdate(addr="10.0.0.1", tags=["db"])
    host = service.update("test-host", update_data)
    
    assert host.addr == "10.0.0.1"
    assert len(host.tags) == 1
    assert host.tags[0].name == "db"

def test_host_service_delete(db_session):
    service = HostService(db_session)
    data = HostCreate(name="test-host", addr="1.2.3.4", user="root", env="dev")
    service.create(data)
    
    service.delete("test-host")
    assert service.get("test-host") is None
