"""Git 工具 - git_status, git_log 等."""

from typing import Any

from .base import MCPTool, ToolResult, ToolStatus
from .ssh import SSHExecTool


class GitStatusTool(MCPTool):
    """查看 Git 仓库状态."""

    def __init__(self, ssh_tool: SSHExecTool | None = None) -> None:
        """初始化 Git 状态工具.

        Args:
            ssh_tool: SSH 执行工具实例（远程仓库用）
        """
        self.ssh_tool = ssh_tool

    @property
    def name(self) -> str:
        """Tool 名称."""
        return "git_status"

    @property
    def description(self) -> str:
        """Tool 描述."""
        return "查看 Git 仓库状态，支持本地和远程仓库"

    @property
    def input_schema(self) -> dict[str, Any]:
        """输入 Schema."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "仓库路径",
                },
                "host": {
                    "type": "string",
                    "description": "远程主机别名（可选，本地仓库不需要）",
                },
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行 Git 状态查询.

        Args:
            path: 仓库路径
            host: 远程主机别名（可选）

        Returns:
            执行结果
        """
        path = kwargs["path"]
        host = kwargs.get("host")

        # 构建命令
        command = f"cd {path} && git status --short && echo '---' && git branch -v"

        if host:
            # 远程仓库
            if not self.ssh_tool:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error="SSH 工具未配置，无法查询远程仓库",
                )
            return await self.ssh_tool.execute(host=host, command=command)
        else:
            # 本地仓库
            import asyncio
            import subprocess

            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return ToolResult(
                    status=ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.ERROR,
                    output=result.stdout,
                    error=result.stderr,
                    exit_code=result.returncode,
                )
            except Exception as e:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"执行失败: {str(e)}",
                )


class GitLogTool(MCPTool):
    """查看 Git 提交历史."""

    def __init__(self, ssh_tool: SSHExecTool | None = None) -> None:
        """初始化 Git 日志工具.

        Args:
            ssh_tool: SSH 执行工具实例（远程仓库用）
        """
        self.ssh_tool = ssh_tool

    @property
    def name(self) -> str:
        """Tool 名称."""
        return "git_log"

    @property
    def description(self) -> str:
        """Tool 描述."""
        return "查看 Git 提交历史"

    @property
    def input_schema(self) -> dict[str, Any]:
        """输入 Schema."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "仓库路径",
                },
                "count": {
                    "type": "integer",
                    "default": 10,
                    "description": "显示最近 N 个提交（默认 10）",
                },
                "branch": {
                    "type": "string",
                    "description": "分支名称（可选，默认当前分支）",
                },
                "host": {
                    "type": "string",
                    "description": "远程主机别名（可选）",
                },
                "oneline": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否使用单行格式",
                },
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行 Git 日志查询.

        Args:
            path: 仓库路径
            count: 提交数量
            branch: 分支名称
            host: 远程主机别名
            oneline: 是否单行格式

        Returns:
            执行结果
        """
        path = kwargs["path"]
        count = kwargs.get("count", 10)
        branch = kwargs.get("branch", "")
        host = kwargs.get("host")
        oneline = kwargs.get("oneline", True)

        # 构建命令
        format_opt = "--oneline" if oneline else "--pretty=format:'%h %s (%an, %ar)'"
        branch_opt = branch if branch else ""
        command = f"cd {path} && git log -{count} {format_opt} {branch_opt}"

        if host:
            # 远程仓库
            if not self.ssh_tool:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error="SSH 工具未配置，无法查询远程仓库",
                )
            return await self.ssh_tool.execute(host=host, command=command)
        else:
            # 本地仓库
            import asyncio
            import subprocess

            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return ToolResult(
                    status=ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.ERROR,
                    output=result.stdout,
                    error=result.stderr,
                    exit_code=result.returncode,
                )
            except Exception as e:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"执行失败: {str(e)}",
                )


class GitDiffTool(MCPTool):
    """查看 Git 文件差异."""

    def __init__(self, ssh_tool: SSHExecTool | None = None) -> None:
        """初始化 Git diff 工具.

        Args:
            ssh_tool: SSH 执行工具实例
        """
        self.ssh_tool = ssh_tool

    @property
    def name(self) -> str:
        """Tool 名称."""
        return "git_diff"

    @property
    def description(self) -> str:
        """Tool 描述."""
        return "查看 Git 文件差异（工作区或提交间）"

    @property
    def input_schema(self) -> dict[str, Any]:
        """输入 Schema."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "仓库路径",
                },
                "file": {
                    "type": "string",
                    "description": "指定文件（可选）",
                },
                "staged": {
                    "type": "boolean",
                    "default": False,
                    "description": "查看已暂存的更改",
                },
                "host": {
                    "type": "string",
                    "description": "远程主机别名（可选）",
                },
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行 Git diff.

        Args:
            path: 仓库路径
            file: 文件路径
            staged: 是否查看已暂存
            host: 远程主机别名

        Returns:
            执行结果
        """
        path = kwargs["path"]
        file = kwargs.get("file", "")
        staged = kwargs.get("staged", False)
        host = kwargs.get("host")

        # 构建命令
        staged_opt = "--staged" if staged else ""
        file_opt = file if file else ""
        command = f"cd {path} && git diff {staged_opt} {file_opt} | head -100"

        if host:
            if not self.ssh_tool:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error="SSH 工具未配置",
                )
            return await self.ssh_tool.execute(host=host, command=command)
        else:
            import asyncio
            import subprocess

            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return ToolResult(
                    status=ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.ERROR,
                    output=result.stdout or "(无差异)",
                    error=result.stderr,
                    exit_code=result.returncode,
                )
            except Exception as e:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"执行失败: {str(e)}",
                )
