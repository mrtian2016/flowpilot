"""日志分析工具 - log_tail 和 log_search."""

import re
from typing import Any

from .base import MCPTool, ToolResult, ToolStatus
from .ssh import SSHExecTool


class LogTailTool(MCPTool):
    """实时查看远程日志文件."""

    def __init__(self, ssh_tool: SSHExecTool) -> None:
        """初始化日志查看工具.

        Args:
            ssh_tool: SSH 执行工具实例
        """
        self.ssh_tool = ssh_tool

    @property
    def name(self) -> str:
        """Tool 名称."""
        return "log_tail"

    @property
    def description(self) -> str:
        """Tool 描述."""
        return "查看远程主机的日志文件最后 N 行，支持关键词过滤"

    @property
    def input_schema(self) -> dict[str, Any]:
        """输入 Schema."""
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "主机别名",
                },
                "path": {
                    "type": "string",
                    "description": "日志文件路径，如 /var/log/nginx/error.log",
                },
                "lines": {
                    "type": "integer",
                    "default": 50,
                    "description": "查看最后 N 行（默认 50）",
                },
                "grep": {
                    "type": "string",
                    "description": "可选：关键词过滤",
                },
            },
            "required": ["host", "path"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行日志查看.

        Args:
            host: 主机别名
            path: 日志文件路径
            lines: 行数
            grep: 过滤关键词

        Returns:
            执行结果
        """
        host = kwargs["host"]
        path = kwargs["path"]
        lines = kwargs.get("lines", 50)
        grep_pattern = kwargs.get("grep")

        # 构建命令
        if grep_pattern:
            # 先 tail 再 grep
            command = f"tail -n {lines * 2} {path} | grep -i '{grep_pattern}' | tail -n {lines}"
        else:
            command = f"tail -n {lines} {path}"

        # 使用 SSH 工具执行
        result = await self.ssh_tool.execute(host=host, command=command)

        # 增强输出信息
        if result.status == ToolStatus.SUCCESS:
            output_lines = result.output.strip().split("\n") if result.output else []
            result.metadata = result.metadata or {}
            result.metadata["line_count"] = len(output_lines)
            result.metadata["path"] = path
            result.metadata["grep"] = grep_pattern

        return result


class LogSearchTool(MCPTool):
    """搜索远程日志文件."""

    def __init__(self, ssh_tool: SSHExecTool) -> None:
        """初始化日志搜索工具.

        Args:
            ssh_tool: SSH 执行工具实例
        """
        self.ssh_tool = ssh_tool

    @property
    def name(self) -> str:
        """Tool 名称."""
        return "log_search"

    @property
    def description(self) -> str:
        """Tool 描述."""
        return "搜索远程日志文件，支持正则、日志级别过滤和时间范围"

    @property
    def input_schema(self) -> dict[str, Any]:
        """输入 Schema."""
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "主机别名",
                },
                "path": {
                    "type": "string",
                    "description": "日志文件路径或通配符（如 /var/log/*.log）",
                },
                "pattern": {
                    "type": "string",
                    "description": "搜索模式（支持正则表达式）",
                },
                "level": {
                    "type": "string",
                    "enum": ["ERROR", "WARN", "INFO", "DEBUG"],
                    "description": "日志级别过滤（可选）",
                },
                "since": {
                    "type": "string",
                    "description": "时间范围，如 10m（分钟）、1h（小时）、1d（天）",
                },
                "context": {
                    "type": "integer",
                    "default": 0,
                    "description": "显示匹配行前后的上下文行数",
                },
                "max_results": {
                    "type": "integer",
                    "default": 50,
                    "description": "最大返回结果数",
                },
            },
            "required": ["host", "path", "pattern"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行日志搜索.

        Args:
            host: 主机别名
            path: 日志路径
            pattern: 搜索模式
            level: 日志级别
            since: 时间范围
            context: 上下文行数
            max_results: 最大结果数

        Returns:
            执行结果
        """
        host = kwargs["host"]
        path = kwargs["path"]
        pattern = kwargs["pattern"]
        level = kwargs.get("level")
        since = kwargs.get("since")
        context = kwargs.get("context", 0)
        max_results = kwargs.get("max_results", 50)

        # 构建 grep 命令
        grep_opts = ["-i"]  # 忽略大小写

        if context > 0:
            grep_opts.append(f"-C {context}")

        # 组合搜索模式
        search_pattern = pattern
        if level:
            # 添加日志级别过滤
            search_pattern = f"({level}|{level.lower()}).*{pattern}|{pattern}.*({level}|{level.lower()})"
            grep_opts.append("-E")  # 使用扩展正则

        grep_cmd = f"grep {' '.join(grep_opts)} '{search_pattern}'"

        # 处理时间范围
        if since:
            # 使用 find 找到最近修改的文件，或用 awk 过滤时间戳
            # 简化处理：使用 tail 取最后一部分日志
            lines_estimate = self._estimate_lines_from_time(since)
            command = f"tail -n {lines_estimate} {path} | {grep_cmd} | tail -n {max_results}"
        else:
            command = f"{grep_cmd} {path} | tail -n {max_results}"

        # 执行搜索
        result = await self.ssh_tool.execute(host=host, command=command)

        # 增强元数据
        if result.status == ToolStatus.SUCCESS:
            output_lines = result.output.strip().split("\n") if result.output else []
            result.metadata = result.metadata or {}
            result.metadata["match_count"] = len([l for l in output_lines if l.strip()])
            result.metadata["pattern"] = pattern
            result.metadata["level"] = level
            result.metadata["since"] = since

        return result

    def _estimate_lines_from_time(self, since: str) -> int:
        """根据时间范围估算行数.

        Args:
            since: 时间范围字符串

        Returns:
            估算的行数
        """
        # 简单估算：假设每分钟约 100 行日志
        match = re.match(r"(\d+)([mhd])", since.lower())
        if not match:
            return 5000

        value = int(match.group(1))
        unit = match.group(2)

        lines_per_minute = 100

        if unit == "m":
            return value * lines_per_minute
        elif unit == "h":
            return value * 60 * lines_per_minute
        elif unit == "d":
            return value * 24 * 60 * lines_per_minute

        return 5000


class DockerLogsTool(MCPTool):
    """查看 Docker 容器日志."""

    def __init__(self, ssh_tool: SSHExecTool) -> None:
        """初始化 Docker 日志工具.

        Args:
            ssh_tool: SSH 执行工具实例
        """
        self.ssh_tool = ssh_tool

    @property
    def name(self) -> str:
        """Tool 名称."""
        return "docker_logs"

    @property
    def description(self) -> str:
        """Tool 描述."""
        return "查看 Docker 容器的日志"

    @property
    def input_schema(self) -> dict[str, Any]:
        """输入 Schema."""
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "主机别名",
                },
                "container": {
                    "type": "string",
                    "description": "容器名称或 ID",
                },
                "tail": {
                    "type": "integer",
                    "default": 100,
                    "description": "查看最后 N 行（默认 100）",
                },
                "since": {
                    "type": "string",
                    "description": "时间范围，如 10m、1h、2024-01-01",
                },
                "grep": {
                    "type": "string",
                    "description": "关键词过滤（可选）",
                },
            },
            "required": ["host", "container"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行 Docker 日志查看.

        Args:
            host: 主机别名
            container: 容器名称或 ID
            tail: 行数
            since: 时间范围
            grep: 过滤关键词

        Returns:
            执行结果
        """
        host = kwargs["host"]
        container = kwargs["container"]
        tail = kwargs.get("tail", 100)
        since = kwargs.get("since")
        grep_pattern = kwargs.get("grep")

        # 构建 docker logs 命令
        docker_opts = [f"--tail {tail}"]

        if since:
            docker_opts.append(f"--since {since}")

        command = f"docker logs {' '.join(docker_opts)} {container}"

        # 添加 grep 过滤
        if grep_pattern:
            command = f"{command} 2>&1 | grep -i '{grep_pattern}'"
        else:
            command = f"{command} 2>&1"

        # 执行命令
        result = await self.ssh_tool.execute(host=host, command=command)

        # 增强元数据
        if result.status == ToolStatus.SUCCESS:
            result.metadata = result.metadata or {}
            result.metadata["container"] = container
            result.metadata["tail"] = tail

        return result
