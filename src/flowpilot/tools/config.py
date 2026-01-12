"""配置管理工具 - 通过 Agent 对话管理配置."""

from typing import Any

from flowpilot.core.db import SessionLocal
from flowpilot.core.models import Host, Tag
from flowpilot.config.loader import load_config as get_config
from .base import MCPTool, ToolResult, ToolStatus


class HostAddTool(MCPTool):
    """添加主机配置."""

    @property
    def name(self) -> str:
        return "host_add"

    @property
    def description(self) -> str:
        return "添加一台新主机到配置中 (保存到数据库)"

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
            with SessionLocal() as db:
                # 检查是否存在
                existing = db.query(Host).filter_by(name=alias).first()
                if existing:
                     return ToolResult(status=ToolStatus.ERROR, error=f"主机 '{alias}' 已存在于数据库中")
                
                # 创建新主机
                host = Host(
                    name=alias,
                    env=env,
                    user=user,
                    addr=addr,
                    port=port,
                    jump=jump,
                    description=description,
                    group=group
                )
                db.add(host)
                db.commit()

            return ToolResult(
                status=ToolStatus.SUCCESS,
                output=f"✅ 已添加主机到数据库: {alias}\n  地址: {user}@{addr}\n  环境: {env}\n  分组: {group}\n  备注: {description}",
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
        return "列出所有配置的主机 (YAML + DB)，支持按分组或环境过滤"

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
            # 使用混合加载器获取完整配置
            config = get_config()
            hosts = config.hosts

            if not hosts:
                return ToolResult(status=ToolStatus.SUCCESS, output="暂无配置的主机")

            # 按分组组织
            grouped: dict[str, list[str]] = {}
            for alias, host in hosts.items():
                # Filter
                if group_filter and host.group != group_filter:
                    continue
                if env_filter and host.env != env_filter:
                    continue

                g = host.group or "default"
                if g not in grouped:
                    grouped[g] = []
                
                desc = f" - {host.description}" if host.description else ""
                host_info = f"[{host.env}] {alias}: {host.user}@{host.addr}{desc}"
                grouped[g].append(host_info)

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
        return "从数据库中移除一台主机 (注: 无法移除 config.yaml 中的只读配置)"

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
            with SessionLocal() as db:
                host = db.query(Host).filter_by(name=alias).first()
                if not host:
                    return ToolResult(status=ToolStatus.ERROR, error=f"数据库中未找到主机 '{alias}' (若是 config.yaml 中的配置则无法直接删除)")
                
                db.delete(host)
                db.commit()

            return ToolResult(status=ToolStatus.SUCCESS, output=f"✅ 已从数据库移除主机: {alias}")

        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=f"移除主机失败: {e}")


class HostUpdateTool(MCPTool):
    """更新主机配置."""

    @property
    def name(self) -> str:
        return "host_update"

    @property
    def description(self) -> str:
        return "更新主机配置 (将覆盖 config.yaml 中同名配置)"

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
            updates = []
            with SessionLocal() as db:
                host = db.query(Host).filter_by(name=alias).first()
                
                # 如果数据库没有，可能是想覆盖 YAML 中的配置，我们需要新建一个条目
                if not host:
                    # 先看 YAML 里有没有 (从 ConfigLoader 读)
                    config = get_config()
                    if alias not in config.hosts:
                         return ToolResult(status=ToolStatus.ERROR, error=f"主机 '{alias}' 不存在")
                    
                    # 从 YAML 复制基本信息到 DB 用于覆盖
                    yaml_host = config.hosts[alias]
                    host = Host(
                        name=alias,
                        env=yaml_host.env,
                        user=yaml_host.user,
                        addr=yaml_host.addr,
                        port=yaml_host.port,
                        jump=yaml_host.jump,
                        description=yaml_host.description,
                        group=yaml_host.group or "default",
                        ssh_key=yaml_host.ssh_key
                    )
                    db.add(host)
                    updates.append("(从 YAML 复制并创建数据库覆盖项)")

                if "description" in kwargs:
                    host.description = kwargs["description"]
                    updates.append(f"备注: {kwargs['description']}")
                if "group" in kwargs:
                    host.group = kwargs["group"]
                    updates.append(f"分组: {kwargs['group']}")
                if "env" in kwargs:
                    host.env = kwargs["env"]
                    updates.append(f"环境: {kwargs['env']}")

                if not updates:
                    return ToolResult(status=ToolStatus.SUCCESS, output="未指定要更新的字段")

                db.commit()

            return ToolResult(status=ToolStatus.SUCCESS, output=f"✅ 已更新主机 {alias}:\n  " + "\n  ".join(updates))

        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=f"更新失败: {e}")
