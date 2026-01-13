import pytest
from unittest.mock import MagicMock, patch
from flowpilot.tools.config import HostAddTool, HostUpdateTool
from flowpilot.tools.service import ServiceListTool
from flowpilot.core.services.host_service import HostService
from flowpilot.core.schemas import HostCreate
from flowpilot.core.models import Host, HostService as HostServiceModel

# Mock SessionLocal to return a mock session
@pytest.fixture
def mock_db_session():
    session = MagicMock()
    # Mock query... returns object with filter_by...
    return session

@pytest.mark.asyncio
async def test_host_add_tool(mock_db_session):
    with patch("flowpilot.tools.config.SessionLocal") as mock_session_local:
        mock_session_local.return_value.__enter__.return_value = mock_db_session
        
        # Mock HostService to avoid real DB calls logic if we want pure unit test of Tool wrapper
        # But we want to test Tool -> Service integration somewhat.
        # However, Service uses DB. So we need real DB session or mocked DB session.
        # Let's mock the Service class itself to verify Tool calls Service correctly.
        
        with patch("flowpilot.tools.config.HostService") as match_host_service:
            mock_service_instance = match_host_service.return_value
            
            tool = HostAddTool()
            result = await tool.execute(
                alias="test-host",
                addr="1.2.3.4",
                user="root",
                env="dev"
            )
            
            assert result.status == "success"
            mock_service_instance.create.assert_called_once()
            call_args = mock_service_instance.create.call_args[0][0]
            assert isinstance(call_args, HostCreate)
            assert call_args.name == "test-host"

@pytest.mark.asyncio
async def test_service_list_tool(mock_db_session):
    with patch("flowpilot.tools.service.SessionLocal") as mock_session_local:
        mock_session_local.return_value.__enter__.return_value = mock_db_session
        
        with patch("flowpilot.tools.service.HostService") as match_host_service:
            mock_service_instance = match_host_service.return_value
            
            # Setup return value of search_services
            mock_host = MagicMock(spec=Host)
            mock_host.name = "host1"
            mock_host.description = "desc1"
            
            mock_svc = MagicMock(spec=HostServiceModel)
            mock_svc.name = "my-service"
            mock_svc.service_name = "svc"
            mock_svc.service_type = "systemd"
            mock_svc.description = "desc"
            mock_svc.host = mock_host
            
            mock_service_instance.search_services.return_value = [mock_svc]
            
            tool = ServiceListTool()
            result = await tool.execute(host="host1")
            
            assert result.status == "success"
            assert "my-service" in result.output
            mock_service_instance.search_services.assert_called_with(q_host="host1", q_service="")
