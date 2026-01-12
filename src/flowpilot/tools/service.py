"""服务管理工具 - 让 AI 能够列出和控制主机上的服务."""

from typing import Any

from flowpilot.config.loader import load_config
from flowpilot.core.db import SessionLocal
from flowpilot.core.models import Host, HostService

from .base import MCPTool, ToolResult, ToolStatus
from .ssh import SSHExecTool


class ServiceListTool(MCPTool):
    """列出主机服务的工具."""

    @property
    def name(self) -> str:
        return "service_list"

    @property
    def description(self) -> str:
        return "列出主机上配置的服务。可以按主机名、服务名或描述搜索。"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "主机别名或描述关键词（可选，不填则列出所有）",
                },
                "service": {
                    "type": "string",
                    "description": "服务名称关键词（可选）",
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行服务列表查询."""
        host_query = kwargs.get("host", "")
        service_query = kwargs.get("service", "")

        try:
            with SessionLocal() as db:
                query = db.query(HostService).join(Host)

                # 按主机过滤
                if host_query:
                    query = query.filter(
                        (Host.name.ilike(f"%{host_query}%"))
                        | (Host.description.ilike(f"%{host_query}%"))
                    )

                # 按服务过滤
                if service_query:
                    query = query.filter(
                        (HostService.name.ilike(f"%{service_query}%"))
                        | (HostService.service_name.ilike(f"%{service_query}%"))
                        | (HostService.description.ilike(f"%{service_query}%"))
                    )

                services = query.all()

                if not services:
                    return ToolResult(
                        status=ToolStatus.SUCCESS,
                        output="未找到匹配的服务配置。",
                    )

                # 格式化输出
                lines = ["## 主机服务列表\n"]
                current_host = None
                for svc in services:
                    if current_host != svc.host.name:
                        current_host = svc.host.name
                        host_desc = svc.host.description or svc.host.name
                        lines.append(f"\n### {host_desc} (`{svc.host.name}`)\n")

                    lines.append(
                        f"- **{svc.name}**: `{svc.service_name}` ({svc.service_type})"
                    )
                    if svc.description:
                        lines.append(f"  - {svc.description}")

                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    output="\n".join(lines),
                    metadata={"count": len(services)},
                )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"查询服务列表失败: {str(e)}",
            )


class ServiceControlTool(MCPTool):
    """控制主机服务的工具（启动/停止/重启/状态）."""

    def __init__(self, ssh_tool: SSHExecTool) -> None:
        """初始化服务控制工具.

        Args:
            ssh_tool: SSH 执行工具
        """
        self.ssh_tool = ssh_tool

    @property
    def name(self) -> str:
        return "service_control"

    @property
    def description(self) -> str:
        return "控制主机上的服务（启动/停止/重启/查看状态）。需要指定主机和服务名称。"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "主机别名或描述（如 '东勤盘点'、'dq-robot-1'）",
                },
                "service": {
                    "type": "string",
                    "description": "服务名称或描述（如 '后端服务'、'ir_web'）",
                },
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "restart", "status"],
                    "description": "操作类型",
                },
            },
            "required": ["host", "service", "action"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行服务控制操作."""
        host_query = kwargs["host"]
        service_query = kwargs["service"]
        action = kwargs["action"]

        try:
            # 1. 查找匹配的服务
            with SessionLocal() as db:
                query = db.query(HostService).join(Host)

                # 按主机匹配
                query = query.filter(
                    (Host.name.ilike(f"%{host_query}%"))
                    | (Host.description.ilike(f"%{host_query}%"))
                )

                # 按服务匹配
                query = query.filter(
                    (HostService.name.ilike(f"%{service_query}%"))
                    | (HostService.service_name.ilike(f"%{service_query}%"))
                    | (HostService.description.ilike(f"%{service_query}%"))
                )

                services = query.all()

                if not services:
                    return ToolResult(
                        status=ToolStatus.ERROR,
                        error=f"未找到主机 '{host_query}' 上的服务 '{service_query}'。请先使用 service_list 查看可用服务。",
                    )

                if len(services) > 1:
                    # 多个匹配，让用户选择
                    matches = [
                        f"- {s.host.name} ({s.host.description}): {s.name} ({s.service_name})"
                        for s in services
                    ]
                    return ToolResult(
                        status=ToolStatus.ERROR,
                        error=f"找到 {len(services)} 个匹配的服务，请更精确指定:\n"
                        + "\n".join(matches),
                    )

                # 唯一匹配
                matched_service = services[0]
                host_name = matched_service.host.name
                service_name = matched_service.service_name
                service_type = matched_service.service_type

            # 2. 构建命令
            command = self._build_command(service_type, service_name, action)
            if not command:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"不支持的服务类型: {service_type}",
                )

            # 3. 执行 SSH 命令
            result = await self.ssh_tool.execute(host=host_name, command=command)

            # 4. 包装结果
            if result.status == ToolStatus.SUCCESS:
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    output=f"✅ 已对 {matched_service.host.description or host_name} 的 {matched_service.name} 执行 {action}\n\n{result.output}",
                    metadata={
                        "host": host_name,
                        "service": service_name,
                        "action": action,
                    },
                )
            else:
                return result

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"服务控制失败: {str(e)}",
            )

    def _build_command(
        self, service_type: str, service_name: str, action: str
    ) -> str | None:
        """根据服务类型构建控制命令."""
        if service_type == "systemd":
            return f"sudo systemctl {action} {service_name}"
        elif service_type == "docker":
            if action == "status":
                return f"docker ps -f name={service_name}"
            elif action == "restart":
                return f"docker restart {service_name}"
            elif action == "start":
                return f"docker start {service_name}"
            elif action == "stop":
                return f"docker stop {service_name}"
        elif service_type == "pm2":
            if action == "status":
                return f"pm2 show {service_name}"
            else:
                return f"pm2 {action} {service_name}"
        return None
