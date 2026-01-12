"""SSH Config 解析器.

解析 ~/.ssh/config 文件并转换为 FlowPilot 主机配置格式。
"""

import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from flowpilot.core.db import SessionLocal
from flowpilot.core.models import Host, Tag


def parse_ssh_config(config_path: str | Path | None = None) -> list[dict[str, Any]]:
    """解析 SSH config 文件.

    Args:
        config_path: SSH 配置文件路径（默认 ~/.ssh/config）

    Returns:
        解析后的主机列表，每个主机包含：
        - name: 主机别名
        - hostname: 实际地址
        - user: 用户名
        - port: 端口
        - identity_file: 私钥文件
        - proxy_jump: 跳板机
    """
    if config_path is None:
        config_path = Path.home() / ".ssh" / "config"
    else:
        config_path = Path(config_path).expanduser()

    if not config_path.exists():
        return []

    hosts: list[dict[str, Any]] = []
    current_host: dict[str, Any] | None = None

    # 读取配置文件
    content = config_path.read_text(encoding="utf-8")

    for line in content.splitlines():
        line = line.strip()

        # 跳过空行和注释
        if not line or line.startswith("#"):
            continue

        # 处理 Include 指令
        if line.lower().startswith("include"):
            include_pattern = line.split(None, 1)[1] if len(line.split()) > 1 else ""
            # 展开 Include 路径
            if include_pattern:
                include_path = Path(config_path.parent / include_pattern).expanduser()
                # 处理通配符
                if "*" in str(include_path):
                    for matched_path in include_path.parent.glob(include_path.name):
                        hosts.extend(parse_ssh_config(matched_path))
                elif include_path.exists():
                    hosts.extend(parse_ssh_config(include_path))
            continue

        # 解析 Host 行
        if line.lower().startswith("host "):
            # 保存之前的 host
            if current_host and current_host.get("name") not in ("*", "github.com"):
                hosts.append(current_host)

            host_pattern = line.split(None, 1)[1] if len(line.split()) > 1 else ""

            # 跳过通配符和特殊主机
            if host_pattern == "*" or "github" in host_pattern.lower():
                current_host = None
                continue

            current_host = {
                "name": host_pattern,
                "hostname": None,
                "user": None,
                "port": 22,
                "identity_file": None,
                "proxy_jump": None,
            }
            continue

        # 解析主机属性
        if current_host is not None:
            # 使用正则解析 key value
            match = re.match(r"(\w+)\s+(.+)", line, re.IGNORECASE)
            if match:
                key = match.group(1).lower()
                value = match.group(2).strip()

                if key == "hostname":
                    current_host["hostname"] = value
                elif key == "user":
                    current_host["user"] = value
                elif key == "port":
                    try:
                        current_host["port"] = int(value)
                    except ValueError:
                        pass
                elif key == "identityfile":
                    current_host["identity_file"] = value
                elif key in ("proxyjump", "proxycommand"):
                    current_host["proxy_jump"] = value

    # 保存最后一个 host
    if current_host and current_host.get("name") not in ("*", "github.com"):
        hosts.append(current_host)

    return hosts


def convert_to_flowpilot_hosts(
    ssh_hosts: list[dict[str, Any]],
    default_env: str = "dev",
) -> dict[str, dict[str, Any]]:
    """将 SSH hosts 转换为 FlowPilot 配置格式.

    Args:
        ssh_hosts: parse_ssh_config 返回的主机列表
        default_env: 默认环境标签

    Returns:
        FlowPilot hosts 配置字典
    """
    flowpilot_hosts: dict[str, dict[str, Any]] = {}

    for host in ssh_hosts:
        name = host.get("name")
        if not name:
            continue

        # 跳过没有 hostname 的条目
        hostname = host.get("hostname")
        if not hostname:
            continue

        config: dict[str, Any] = {
            "env": default_env,
            "addr": hostname,
        }

        if host.get("user"):
            config["user"] = host["user"]

        if host.get("port") and host["port"] != 22:
            config["port"] = host["port"]

        if host.get("proxy_jump"):
            config["jump"] = host["proxy_jump"]

        flowpilot_hosts[name] = config

    return flowpilot_hosts


def format_hosts_yaml(hosts: dict[str, dict[str, Any]]) -> str:
    """将主机配置格式化为 YAML 字符串.

    Args:
        hosts: FlowPilot hosts 配置

    Returns:
        YAML 格式字符串
    """
    lines = ["hosts:"]

    for name, config in hosts.items():
        lines.append(f"  {name}:")
        for key, value in config.items():
            if isinstance(value, list):
                lines.append(f"    {key}:")
                for item in value:
                    lines.append(f"      - {item}")
            else:
                lines.append(f"    {key}: {value}")
        lines.append("")  # 空行分隔

    return "\n".join(lines)


def save_hosts_to_db(hosts: dict[str, dict[str, Any]]) -> int:
    """Save hosts configuration to database.
    
    Args:
        hosts: FlowPilot hosts configuration
        
    Returns:
        Number of hosts saved
    """
    count = 0
    with SessionLocal() as db:
        for name, config in hosts.items():
            # Check exist
            host = db.query(Host).filter_by(name=name).first()
            if not host:
                host = Host(name=name)
                db.add(host)
                count += 1
            
            host.env = config.get("env", "dev")
            host.user = config.get("user", "root")
            host.addr = config.get("addr", "")
            host.port = config.get("port", 22)
            host.jump = config.get("jump")
            host.ssh_key = config.get("ssh_key")
            host.description = config.get("description", "")
            host.group = config.get("group", "default")
            
            # Simple tag handling (create if not exist)
            if "tags" in config:
                current_tags = []
                for t_name in config["tags"]:
                    tag = db.query(Tag).filter_by(name=t_name).first()
                    if not tag:
                        tag = Tag(name=t_name)
                        db.add(tag)
                    current_tags.append(tag)
                host.tags = current_tags
        
        db.commit()
    return count
