"""Tool 基类和注册表测试."""

import pytest

from flowpilot.tools.base import MCPTool, ToolRegistry, ToolResult, ToolStatus


class MockTool(MCPTool):
    """Mock Tool for testing."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
            },
            "required": ["input"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Mock execution."""
        input_value = kwargs.get("input", "")
        
        if input_value == "error":
            return ToolResult(
                status=ToolStatus.ERROR,
                error="Mock error",
            )
        
        return ToolResult(
            status=ToolStatus.SUCCESS,
            output=f"Processed: {input_value}",
        )


def test_tool_result_success():
    """测试成功的 Tool 结果."""
    result = ToolResult(
        status=ToolStatus.SUCCESS,
        output="Success output",
        exit_code=0,
        duration_sec=1.5,
    )

    assert result.status == ToolStatus.SUCCESS
    assert result.output == "Success output"
    assert result.exit_code == 0
    assert result.duration_sec == 1.5


def test_tool_result_error():
    """测试错误的 Tool 结果."""
    result = ToolResult(
        status=ToolStatus.ERROR,
        error="Something went wrong",
        exit_code=1,
    )

    assert result.status == ToolStatus.ERROR
    assert result.error == "Something went wrong"
    assert result.exit_code == 1


def test_tool_result_pending_confirm():
    """测试需要确认的 Tool 结果."""
    result = ToolResult(
        status=ToolStatus.PENDING_CONFIRM,
        confirm_token="token_123",
        preview={"host": "prod-server", "command": "rm file"},
    )

    assert result.status == ToolStatus.PENDING_CONFIRM
    assert result.confirm_token == "token_123"
    assert result.preview["host"] == "prod-server"


@pytest.mark.asyncio
async def test_mock_tool_execute():
    """测试 Mock Tool 执行."""
    tool = MockTool()

    result = await tool.execute(input="test")

    assert result.status == ToolStatus.SUCCESS
    assert "test" in result.output


@pytest.mark.asyncio
async def test_mock_tool_error():
    """测试 Mock Tool 错误处理."""
    tool = MockTool()

    result = await tool.execute(input="error")

    assert result.status == ToolStatus.ERROR
    assert "Mock error" in result.error


def test_tool_to_mcp_definition():
    """测试 Tool 转换为 MCP 定义."""
    tool = MockTool()

    mcp_def = tool.to_mcp_definition()

    assert mcp_def["name"] == "mock_tool"
    assert mcp_def["description"] == "A mock tool for testing"
    assert "input_schema" in mcp_def
    assert mcp_def["input_schema"]["type"] == "object"


def test_tool_registry_register():
    """测试 Tool 注册."""
    registry = ToolRegistry()
    tool = MockTool()

    registry.register(tool)

    assert registry.get("mock_tool") is not None
    assert registry.get("mock_tool") == tool


def test_tool_registry_get_nonexistent():
    """测试获取不存在的 Tool."""
    registry = ToolRegistry()

    result = registry.get("nonexistent_tool")

    assert result is None


def test_tool_registry_list_tools():
    """测试列出所有 Tool."""
    registry = ToolRegistry()
    tool1 = MockTool()
    
    # 创建第二个 Mock Tool
    class AnotherMockTool(MCPTool):
        @property
        def name(self) -> str:
            return "another_tool"
        
        @property
        def description(self) -> str:
            return "Another tool"
        
        @property
        def input_schema(self) -> dict:
            return {"type": "object"}
        
        async def execute(self, **kwargs) -> ToolResult:
            return ToolResult(status=ToolStatus.SUCCESS)
    
    tool2 = AnotherMockTool()

    registry.register(tool1)
    registry.register(tool2)

    tools = registry.list_tools()

    assert len(tools) == 2
    assert tool1 in tools
    assert tool2 in tools


def test_tool_registry_get_mcp_definitions():
    """测试获取所有 Tool 的 MCP 定义."""
    registry = ToolRegistry()
    tool = MockTool()

    registry.register(tool)

    definitions = registry.get_mcp_definitions()

    assert len(definitions) == 1
    assert definitions[0]["name"] == "mock_tool"
    assert definitions[0]["description"] == "A mock tool for testing"
