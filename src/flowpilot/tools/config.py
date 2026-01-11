"""配置管理工具 - 通过 Agent 对话管理配置."""

from pathlib import Path
from typing import Any

import yaml

from .base import MCPTool, ToolResult, ToolStatus


class HostAddTool(MCPTool):
    """添加主机配置."""

    @property
    def name(self) -> str:
        return "host_add"

    @property
    def description(self) -> str:
        return "添加一台新主机到配置中"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "alias": {"type": "string", "description": "主机别名（如 prod-api-1）"},
                "addr": {"type": "string", "description": "主机地址（IP 或域名）"},
                "user": {"type": "string", "description": "SSH 用户名"},
                "env": {"type": "string", "enum": ["dev", "staging", "prod"], "description": "环境"},
                "description": {"type": "string", "description": "中文备注"},
                "group": {"type": "string", "description": "分组名称"},
                "port": {"type": "integer", "default": 22, "description": "SSH 端口"},
                "jump": {"type": "string", "description": "跳板机别名（可选）"},
            },
            "required": ["alias", "addr", "user", "env"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        alias = kwargs["alias"]
        addr = kwargs["addr"]
        user = kwargs["user"]
        env = kwargs["env"]
        description = kwargs.get("description", "")
        group = kwargs.get("group", "default")
        port = kwargs.get("port", 22)
        jump = kwargs.get("jump")

        try:
            config_path = Path.home() / ".flowpilot" / "config.yaml"
            if not config_path.exists():
                return ToolResult(status=ToolStatus.ERROR, error="配置文件不存在，请先运行 flowpilot init")

            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            if "hosts" not in config:
                config["hosts"] = {}

            if alias in config["hosts"]:
                return ToolResult(status=ToolStatus.ERROR, error=f"主机 '{alias}' 已存在")

            # 添加新主机
            host_config = {
                "env": env,
                "addr": addr,
                "user": user,
                "port": port,
                "description": description,
                "group": group,
            }
            if jump:
                host_config["jump"] = jump

            config["hosts"][alias] = host_config

            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            return ToolResult(
                status=ToolStatus.SUCCESS,
                output=f"✅ 已添加主机: {alias}\n  地址: {user}@{addr}\n  环境: {env}\n  分组: {group}\n  备注: {description}",
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=f"添加主机失败: {e}")


class HostListTool(MCPTool):
    """列出主机配置."""

    @property
    def name(self) -> str:
        return "host_list"

    @property
    def description(self) -> str:
        return "列出所有配置的主机，支持按分组或环境过滤"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "group": {"type": "string", "description": "按分组过滤（可选）"},
                "env": {"type": "string", "description": "按环境过滤（可选）"},
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        group_filter = kwargs.get("group")
        env_filter = kwargs.get("env")

        try:
            config_path = Path.home() / ".flowpilot" / "config.yaml"
            if not config_path.exists():
                return ToolResult(status=ToolStatus.ERROR, error="配置文件不存在")

            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            hosts = config.get("hosts", {})
            if not hosts:
                return ToolResult(status=ToolStatus.SUCCESS, output="暂无配置的主机")

            # 按分组组织
            grouped: dict[str, list[str]] = {}
            for alias, host in hosts.items():
                if group_filter and host.get("group", "default") != group_filter:
                    continue
                if env_filter and host.get("env") != env_filter:
                    continue

                g = host.get("group", "default")
                if g not in grouped:
                    grouped[g] = []
                desc = f" - {host.get('description')}" if host.get("description") else ""
                grouped[g].append(f"[{host['env']}] {alias}: {host['user']}@{host['addr']}{desc}")

            if not grouped:
                return ToolResult(status=ToolStatus.SUCCESS, output="无匹配的主机")

            lines = []
            for grp, hosts_list in sorted(grouped.items()):
                lines.append(f"【{grp}】")
                for h in hosts_list:
                    lines.append(f"  {h}")

            return ToolResult(status=ToolStatus.SUCCESS, output="\n".join(lines))

        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=f"读取配置失败: {e}")


class HostRemoveTool(MCPTool):
    """移除主机配置."""

    @property
    def name(self) -> str:
        return "host_remove"

    @property
    def description(self) -> str:
        return "从配置中移除一台主机"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "alias": {"type": "string", "description": "要移除的主机别名"},
            },
            "required": ["alias"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        alias = kwargs["alias"]

        try:
            config_path = Path.home() / ".flowpilot" / "config.yaml"
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            if alias not in config.get("hosts", {}):
                return ToolResult(status=ToolStatus.ERROR, error=f"主机 '{alias}' 不存在")

            del config["hosts"][alias]

            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            return ToolResult(status=ToolStatus.SUCCESS, output=f"✅ 已移除主机: {alias}")

        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=f"移除主机失败: {e}")


class HostUpdateTool(MCPTool):
    """更新主机配置."""

    @property
    def name(self) -> str:
        return "host_update"

    @property
    def description(self) -> str:
        return "更新主机配置（如修改分组、备注等）"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "alias": {"type": "string", "description": "主机别名"},
                "description": {"type": "string", "description": "新的中文备注"},
                "group": {"type": "string", "description": "新的分组"},
                "env": {"type": "string", "description": "新的环境"},
            },
            "required": ["alias"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        alias = kwargs["alias"]

        try:
            config_path = Path.home() / ".flowpilot" / "config.yaml"
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            if alias not in config.get("hosts", {}):
                return ToolResult(status=ToolStatus.ERROR, error=f"主机 '{alias}' 不存在")

            host = config["hosts"][alias]
            updates = []

            if "description" in kwargs:
                host["description"] = kwargs["description"]
                updates.append(f"备注: {kwargs['description']}")
            if "group" in kwargs:
                host["group"] = kwargs["group"]
                updates.append(f"分组: {kwargs['group']}")
            if "env" in kwargs:
                host["env"] = kwargs["env"]
                updates.append(f"环境: {kwargs['env']}")

            if not updates:
                return ToolResult(status=ToolStatus.SUCCESS, output="未指定要更新的字段")

            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            return ToolResult(status=ToolStatus.SUCCESS, output=f"✅ 已更新主机 {alias}:\n  " + "\n  ".join(updates))

        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=f"更新失败: {e}")
