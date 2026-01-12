"""HTTP integration tests for MCP Server."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from flowpilot.core.models import Host
from flowpilot.mcp.server import app


@pytest.fixture(name="client")
def client_fixture():
    """Create TestClient for FastAPI app."""
    with TestClient(app) as client:
        yield client


def test_health_endpoint(client: TestClient):
    """Test /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "tools_count" in data


def test_tools_list_via_http(client: TestClient, session: Session):
    """Test tools/list via HTTP JSON-RPC."""
    # JSON-RPC request
    request_data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    response = client.post("/message?session_id=test-session", json=request_data)
    assert response.status_code == 200
    
    data = response.json()
    assert "result" in data
    assert "tools" in data["result"]
    
    tool_names = [t["name"] for t in data["result"]["tools"]]
    assert "host_add" in tool_names
    assert "host_list" in tool_names
    assert "ssh_exec" in tool_names


def test_host_add_via_http(client: TestClient, session: Session):
    """Test host_add tool via HTTP JSON-RPC."""
    request_data = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "host_add",
            "arguments": {
                "alias": "http-test-host",
                "addr": "192.168.1.100",
                "user": "admin",
                "env": "dev",
                "description": "HTTP Test Host"
            }
        }
    }
    
    response = client.post("/message?session_id=test-session", json=request_data)
    assert response.status_code == 200
    
    data = response.json()
    assert "result" in data
    assert not data["result"].get("isError", False)
    assert "已添加主机" in data["result"]["content"][0]["text"]
    
    # Verify in DB
    host = session.query(Host).filter_by(name="http-test-host").first()
    assert host is not None
    assert host.addr == "192.168.1.100"


def test_host_list_via_http(client: TestClient, session: Session):
    """Test host_list tool via HTTP JSON-RPC."""
    # Add test host first
    host = Host(
        name="list-test-host",
        env="staging",
        user="testuser",
        addr="10.0.0.50",
        port=22,
        description="List Test Host",
        group="test"
    )
    session.add(host)
    session.commit()
    
    request_data = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "host_list",
            "arguments": {"env": "staging"}
        }
    }
    
    response = client.post("/message?session_id=test-session", json=request_data)
    assert response.status_code == 200
    
    data = response.json()
    assert "result" in data
    assert not data["result"].get("isError", False)
    
    content = data["result"]["content"][0]["text"]
    assert "list-test-host" in content
    assert "10.0.0.50" in content


def test_initialize_via_http(client: TestClient):
    """Test initialize method via HTTP JSON-RPC."""
    request_data = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    response = client.post("/message?session_id=test-session", json=request_data)
    assert response.status_code == 200
    
    data = response.json()
    assert "result" in data
    assert "protocolVersion" in data["result"]
    assert "serverInfo" in data["result"]
