"""MCP 统一注册管理器."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from flowpilot.config.loader import load_config
from flowpilot.config.schema import FlowPilotConfig
from flowpilot.policy.engine import PolicyEngine
from flowpilot.tools.base import MCPTool, ToolRegistry, ToolResult

from .protocol import (
    PromptArgument,
    PromptDefinition,
    PromptMessage,
    ResourceDefinition,
    TextContent,
)


class MCPResource:
    """MCP Resource 定义."""

    def __init__(
        self,
        uri: str,
        name: str,
        description: str,
        mime_type: str = "application/json",
        handler: Callable[[], Awaitable[str]] | None = None,
    ) -> None:
        self.uri = uri
        self.name = name
        self.description = description
        self.mime_type = mime_type
        self._handler = handler

    async def read(self) -> str:
        """读取资源内容."""
        if self._handler:
            return await self._handler()
        return ""

    def to_definition(self) -> ResourceDefinition:
        """转换为协议定义."""
        return ResourceDefinition(
            uri=self.uri,
            name=self.name,
            description=self.description,
            mimeType=self.mime_type,
        )


class MCPPrompt:
    """MCP Prompt 定义."""

    def __init__(
        self,
        name: str,
        description: str,
        arguments: list[PromptArgument] | None = None,
        template: str = "",
    ) -> None:
        self.name = name
        self.description = description
        self.arguments = arguments or []
        self.template = template

    def render(self, args: dict[str, str] | None = None) -> list[PromptMessage]:
        """渲染 Prompt."""
        args = args or {}
        text = self.template
        for key, value in args.items():
            text = text.replace(f"{{{key}}}", value)
        return [
            PromptMessage(
                role="user",
                content=TextContent(text=text),
            )
        ]

    def to_definition(self) -> PromptDefinition:
        """转换为协议定义."""
        return PromptDefinition(
            name=self.name,
            description=self.description,
            arguments=self.arguments if self.arguments else None,
        )


class MCPRegistry:
    """MCP 统一注册管理器 - 管理 Tools, Resources, Prompts."""

    def __init__(self) -> None:
        """初始化注册器."""
        self._tool_registry = ToolRegistry()
        self._resources: dict[str, MCPResource] = {}
        self._prompts: dict[str, MCPPrompt] = {}
        self._config: FlowPilotConfig | None = None
        self._policy_engine: PolicyEngine | None = None
        self._initialized = False

    def initialize(self) -> None:
        """初始化：加载配置并注册所有组件."""
        if self._initialized:
            return

        # 加载配置
        self._config = load_config()
        self._policy_engine = PolicyEngine(self._config)

        # 注册 Tools
        self._register_tools()

        # 注册 Resources
        self._register_resources()

        # 注册 Prompts
        self._register_prompts()

        self._initialized = True

    @property
    def config(self) -> FlowPilotConfig:
        """获取配置."""
        if not self._config:
            raise RuntimeError("MCPRegistry 未初始化")
        return self._config

    @property
    def policy_engine(self) -> PolicyEngine:
        """获取策略引擎."""
        if not self._policy_engine:
            raise RuntimeError("MCPRegistry 未初始化")
        return self._policy_engine

    # ========== Tools ==========
    def _register_tools(self) -> None:
        """注册所有 Tools."""
        from flowpilot.tools.config import (
            HostAddTool,
            HostListTool,
            HostRemoveTool,
            HostUpdateTool,
        )
        from flowpilot.tools.git import GitDiffTool, GitLogTool, GitStatusTool
        from flowpilot.tools.logs import DockerLogsTool, LogSearchTool, LogTailTool
        from flowpilot.tools.ssh import SSHExecBatchTool, SSHExecTool

        # SSH Tools
        ssh_tool = SSHExecTool(self.policy_engine)
        self._tool_registry.register(ssh_tool)
        self._tool_registry.register(SSHExecBatchTool(self.policy_engine))

        # Log Tools
        self._tool_registry.register(LogTailTool(ssh_tool))
        self._tool_registry.register(LogSearchTool(ssh_tool))
        self._tool_registry.register(DockerLogsTool(ssh_tool))

        # Git Tools
        self._tool_registry.register(GitStatusTool(ssh_tool))
        self._tool_registry.register(GitLogTool(ssh_tool))
        self._tool_registry.register(GitDiffTool(ssh_tool))

        # Config Tools
        self._tool_registry.register(HostAddTool())
        self._tool_registry.register(HostListTool())
        self._tool_registry.register(HostRemoveTool())
        self._tool_registry.register(HostUpdateTool())

    def get_tool(self, name: str) -> MCPTool | None:
        """获取 Tool."""
        return self._tool_registry.get(name)

    def list_tools(self) -> list[MCPTool]:
        """列出所有 Tools."""
        return self._tool_registry.list_tools()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """调用 Tool."""
        tool = self._tool_registry.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' 未找到")
        return await tool.execute(**arguments)

    # ========== Resources ==========
    def _register_resources(self) -> None:
        """注册所有 Resources."""
        # 主机列表资源
        self._resources["flowpilot://hosts"] = MCPResource(
            uri="flowpilot://hosts",
            name="主机列表",
            description="FlowPilot 配置的所有主机",
            handler=self._get_hosts_resource,
        )

        # 服务列表资源
        self._resources["flowpilot://services"] = MCPResource(
            uri="flowpilot://services",
            name="服务列表",
            description="FlowPilot 配置的所有服务",
            handler=self._get_services_resource,
        )

        # 策略列表资源
        self._resources["flowpilot://policies"] = MCPResource(
            uri="flowpilot://policies",
            name="策略规则",
            description="FlowPilot 安全策略规则",
            handler=self._get_policies_resource,
        )

        # 跳板机配置资源
        self._resources["flowpilot://jumps"] = MCPResource(
            uri="flowpilot://jumps",
            name="跳板机列表",
            description="FlowPilot 配置的跳板机",
            handler=self._get_jumps_resource,
        )

    async def _get_hosts_resource(self) -> str:
        """获取主机列表资源."""
        hosts_data = {}
        for name, host in self.config.hosts.items():
            hosts_data[name] = {
                "env": host.env,
                "user": host.user,
                "addr": host.addr,
                "port": host.port,
                "group": host.group,
                "description": host.description,
                "tags": host.tags,
            }
        return json.dumps(hosts_data, ensure_ascii=False, indent=2)

    async def _get_services_resource(self) -> str:
        """获取服务列表资源."""
        services_data = {}
        for name, service in self.config.services.items():
            services_data[name] = service.model_dump()
        return json.dumps(services_data, ensure_ascii=False, indent=2)

    async def _get_policies_resource(self) -> str:
        """获取策略规则资源."""
        policies = [p.model_dump() for p in self.config.policies]
        return json.dumps(policies, ensure_ascii=False, indent=2)

    async def _get_jumps_resource(self) -> str:
        """获取跳板机资源."""
        jumps_data = {}
        for name, jump in self.config.jumps.items():
            jumps_data[name] = jump.model_dump()
        return json.dumps(jumps_data, ensure_ascii=False, indent=2)

    def get_resource(self, uri: str) -> MCPResource | None:
        """获取 Resource."""
        return self._resources.get(uri)

    def list_resources(self) -> list[MCPResource]:
        """列出所有 Resources."""
        return list(self._resources.values())

    # ========== Prompts ==========
    def _register_prompts(self) -> None:
        """注册所有 Prompts."""
        # 排查服务问题
        self._prompts["troubleshoot_service"] = MCPPrompt(
            name="troubleshoot_service",
            description="排查服务故障的引导式 Prompt",
            arguments=[
                PromptArgument(name="service", description="服务名称", required=True),
                PromptArgument(name="symptom", description="故障现象", required=True),
            ],
            template="""请帮我排查 {service} 服务的问题。

故障现象：{symptom}

请按以下步骤进行排查：
1. 首先检查服务所在主机的状态（使用 ssh_exec 执行 uptime、df -h、free -m）
2. 查看服务的近期日志（使用 log_tail 或 docker_logs）
3. 检查是否有相关的错误日志（使用 log_search 搜索 ERROR 关键词）
4. 根据日志分析可能的原因并给出建议
""",
        )

        # 批量操作确认
        self._prompts["batch_operation"] = MCPPrompt(
            name="batch_operation",
            description="批量操作前的安全确认 Prompt",
            arguments=[
                PromptArgument(name="operation", description="操作描述", required=True),
                PromptArgument(name="targets", description="目标主机（逗号分隔）", required=True),
            ],
            template="""我需要在多台主机上执行批量操作。

操作内容：{operation}
目标主机：{targets}

请帮我：
1. 先使用 host_list 确认这些主机的环境（dev/staging/prod）
2. 如果包含 prod 环境主机，请提醒我确认
3. 建议先在一台主机上测试
4. 确认后使用 ssh_exec_batch 执行
""",
        )

        # 日志分析
        self._prompts["analyze_logs"] = MCPPrompt(
            name="analyze_logs",
            description="分析日志并总结问题",
            arguments=[
                PromptArgument(name="host", description="主机别名", required=True),
                PromptArgument(name="log_path", description="日志路径", required=True),
                PromptArgument(
                    name="time_range", description="时间范围（如 1h, 30m）", required=False
                ),
            ],
            template="""请帮我分析主机 {host} 上的日志文件 {log_path}。

时间范围：{time_range}

请：
1. 使用 log_tail 查看最近的日志
2. 使用 log_search 搜索 ERROR 和 WARN 级别的日志
3. 总结发现的问题
4. 给出可能的原因和建议
""",
        )

        # 主机健康检查
        self._prompts["health_check"] = MCPPrompt(
            name="health_check",
            description="主机健康检查 Prompt",
            arguments=[
                PromptArgument(name="host", description="主机别名或 @group", required=True),
            ],
            template="""请对主机 {host} 进行健康检查。

检查项目：
1. 系统负载（uptime）
2. 磁盘使用（df -h）
3. 内存使用（free -m）
4. 网络连通性（ping 关键服务）
5. 重要服务状态（systemctl status）

请使用 ssh_exec 执行检查，并汇总报告。
""",
        )

    def get_prompt(self, name: str) -> MCPPrompt | None:
        """获取 Prompt."""
        return self._prompts.get(name)

    def list_prompts(self) -> list[MCPPrompt]:
        """列出所有 Prompts."""
        return list(self._prompts.values())


# 全局注册器实例
mcp_registry = MCPRegistry()
