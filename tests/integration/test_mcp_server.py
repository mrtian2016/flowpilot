
import pytest
from sqlalchemy.orm import Session
from flowpilot.core.models import Host
from flowpilot.mcp.registry import mcp_registry
from flowpilot.mcp.handlers.tools import handle_tools_list, handle_tools_call
from flowpilot.mcp.protocol import ToolCallParams
from flowpilot.tools.base import ToolStatus

# Ensure registry is initialized
@pytest.fixture(autouse=True)
def init_registry():
    mcp_registry.initialize()

@pytest.mark.asyncio
async def test_tools_list(session: Session):
    """Test tools/list endpoint."""
    result = await handle_tools_list()
    assert result.tools
    
    tool_names = [t.name for t in result.tools]
    assert "host_add" in tool_names
    assert "host_list" in tool_names
    assert "ssh_exec" in tool_names

@pytest.mark.asyncio
async def test_host_add_and_list_integration(session: Session):
    """Test adding a host and then listing it via MCP tools."""
    
    # 1. Add Host
    add_params = ToolCallParams(
        name="host_add",
        arguments={
            "alias": "integration-test-host",
            "addr": "10.0.0.1",
            "user": "admin",
            "env": "prod",
            "description": "Integration Test Host"
        }
    )
    
    result = await handle_tools_call(add_params)
    assert not result.isError
    assert "已添加主机" in result.content[0].text
    
    # Verify in DB directly
    host = session.query(Host).filter_by(name="integration-test-host").first()
    assert host is not None
    assert host.addr == "10.0.0.1"
    
    # 2. List Host
    list_params = ToolCallParams(
        name="host_list",
        arguments={"env": "prod"}
    )
    
    list_result = await handle_tools_call(list_params)
    assert not list_result.isError
    assert "integration-test-host" in list_result.content[0].text
    assert "10.0.0.1" in list_result.content[0].text

@pytest.mark.asyncio
async def test_ssh_exec_dynamic_config(session: Session):
    """Test that ssh_exec sees the newly added host (dynamic config check)."""
    
    # 1. Add Host via DB (simulating setup)
    host = Host(
        name="ssh-test-host",
        env="dev",
        user="testuser",
        addr="127.0.0.1",
        port=22,
        description="SSH Test Host",
        group="test"
    )
    session.add(host)
    session.commit()
    
    # 2. Call SSH Exec
    # Note: We expect connection failure, but NOT "Host not found" error.
    ssh_params = ToolCallParams(
        name="ssh_exec",
        arguments={
            "host": "ssh-test-host",
            "command": "echo hello",
            "timeout": 1
        }
    )
    
    result = await handle_tools_call(ssh_params)
    
    # It should fail because 127.0.0.1:22 is likely not accepting our keys or not reachable in this env
    # But critical check is: Did it find the host?
    # If host not found, error message contains "未找到"
    
    error_msg = result.content[0].text
    
    assert "未找到" not in error_msg
    # It might fail with timeout or auth error
    assert result.isError  # Expected error
