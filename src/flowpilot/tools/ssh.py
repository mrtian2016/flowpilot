"""SSH 工具实现 - ssh_exec 和 ssh_exec_batch."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import paramiko
from paramiko.ssh_exception import (
    AuthenticationException,
    NoValidConnectionsError,
    SSHException,
)

from ..config.loader import load_config
from ..config.schema import FlowPilotConfig, HostConfig
from ..policy.action_classifier import classify_command
from ..policy.engine import PolicyDecision, PolicyEffect, PolicyEngine
from .base import MCPTool, ToolResult, ToolStatus


class SSHExecTool(MCPTool):
    """SSH 命令执行 Tool."""

    def __init__(self, policy_engine: PolicyEngine) -> None:
        """初始化 SSH Tool.

        Args:
            policy_engine: 策略引擎
        """
        self.policy_engine = policy_engine

    @property
    def name(self) -> str:
        """Tool 名称."""
        return "ssh_exec"

    @property
    def description(self) -> str:
        """Tool 描述."""
        return "在远程主机执行 SSH 命令，支持配置别名和跳板机"

    @property
    def input_schema(self) -> dict[str, Any]:
        """输入 Schema."""
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "主机别名（如 prod-api-3）或地址",
                },
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令",
                },
                "env": {
                    "type": "string",
                    "enum": ["dev", "staging", "prod"],
                    "description": "环境（影响策略检查）",
                },
                "timeout": {
                    "type": "integer",
                    "default": 30,
                    "description": "超时时间（秒）",
                },
                "_confirm_token": {
                    "type": "string",
                    "description": "确认 token（策略要求确认时使用）",
                },
            },
            "required": ["host", "command"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行 SSH 命令.

        Args:
            host: 主机别名或地址
            command: 要执行的命令
            env: 环境（可选，用于策略检查）
            timeout: 超时时间（秒）
            _confirm_token: 确认 token（可选）

        Returns:
            执行结果
        """
        # 动态加载配置
        config = load_config()

        host_alias = kwargs["host"]
        command = kwargs["command"]
        env = kwargs.get("env")
        timeout = kwargs.get("timeout", 30)
        confirm_token = kwargs.get("_confirm_token")

        # 1. 解析主机配置
        host_config = self._resolve_host(host_alias, config)
        if not host_config:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"主机 '{host_alias}' 未找到。请检查配置文件中的 hosts 配置。",
            )

        # 自动推断环境（如果未指定）
        if not env:
            env = host_config.env

        # 2. 分类命令
        action_type = classify_command(command)

        # 3. 策略检查
        decision = self.policy_engine.check(
            tool_name=self.name,
            args={"host": host_alias, "command": command, "env": env},
            env=env,
            action_type=action_type,
        )

        # 4. 处理策略决策
        if decision.effect == PolicyEffect.DENY:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"操作被策略拒绝: {decision.message}",
                metadata={"policy_decision": decision},
            )

        if decision.effect == PolicyEffect.REQUIRE_CONFIRM:
            # 检查是否已提供确认 token
            if not confirm_token or not self.policy_engine.validate_confirm_token(confirm_token):
                # 返回待确认状态
                return ToolResult(
                    status=ToolStatus.PENDING_CONFIRM,
                    confirm_token=decision.confirm_token,
                    preview={
                        "host_info": f"{host_alias} ({host_config.addr})",
                        "command": command,
                        "action_type": action_type.value,
                        "env": env,
                        "risk_level": decision.risk_level,
                        "message": decision.message,
                    },
                    metadata={"policy_decision": decision},
                )

            # 消费确认 token
            self.policy_engine.consume_confirm_token(confirm_token)

        # 5. 执行 SSH 命令
        try:
            start_time = time.time()
            exit_code, stdout, stderr = await self._execute_ssh(
                host_config=host_config,
                command=command,
                config=config,
                timeout=timeout,
            )
            duration = time.time() - start_time

            # 判断是否成功
            if exit_code == 0:
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    output=stdout,
                    error=stderr,
                    exit_code=exit_code,
                    duration_sec=duration,
                    metadata={
                        "host": host_alias,
                        "resolved_addr": host_config.addr,
                        "jump_used": host_config.jump,
                        "user": host_config.user,
                    },
                )
            else:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    output=stdout,
                    error=stderr or f"命令执行失败，退出码: {exit_code}",
                    exit_code=exit_code,
                    duration_sec=duration,
                )

        except NoValidConnectionsError as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"⚠️ SSH 连接失败: 无法连接到主机 {host_alias}。可能原因：1) 机器未开机 2) 网络不通 3) SSH服务未运行。原始错误: {str(e)}",
            )
        except AuthenticationException as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"⚠️ SSH 认证失败: 主机 {host_alias} 拒绝了认证。可能原因：1) SSH密钥不正确 2) 用户名错误。原始错误: {str(e)}",
            )
        except SSHException as e:
            error_msg = str(e)
            if "banner" in error_msg.lower() or "protocol" in error_msg.lower():
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"⚠️ SSH 连接失败: 主机 {host_alias} 无法建立SSH连接（无法读取SSH协议banner）。可能原因：1) 机器未开机或正在启动中 2) SSH服务未运行 3) 防火墙阻止了连接 4) 网络连接中断。原始错误: {error_msg}",
                )
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"⚠️ SSH 连接异常: 主机 {host_alias}。原始错误: {error_msg}",
            )
        except TimeoutError:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"⚠️ SSH 连接超时: 主机 {host_alias} 连接超时。可能原因：1) 机器未开机 2) 网络不通 3) 防火墙阻止连接。",
            )
        except ConnectionRefusedError:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"⚠️ SSH 连接被拒绝: 主机 {host_alias} 拒绝了连接。可能原因：1) SSH服务未运行 2) 端口配置错误。",
            )
        except EOFError:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"⚠️ SSH 连接中断: 主机 {host_alias} 连接意外关闭。可能原因：1) 机器未开机 2) SSH服务崩溃 3) 网络中断。",
            )
        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"⚠️ SSH 执行失败: 主机 {host_alias}。错误类型: {type(e).__name__}，详情: {str(e)}",
            )

    def _resolve_host(self, host_alias: str, config: FlowPilotConfig) -> HostConfig | None:
        """解析主机配置.

        Args:
            host_alias: 主机别名
            config: 配置对象

        Returns:
            主机配置，或 None
        """
        return config.hosts.get(host_alias)

    async def _execute_ssh(
        self,
        host_config: HostConfig,
        command: str,
        config: FlowPilotConfig,
        timeout: int = 30,
    ) -> tuple[int, str, str]:
        """执行 SSH 命令（支持跳板机）.

        Args:
            host_config: 主机配置
            command: 命令
            config: 配置对象
            timeout: 超时时间

        Returns:
            (exit_code, stdout, stderr)
        """
        # 使用线程池执行阻塞的 SSH 操作
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(
                executor,
                self._ssh_execute_sync,
                host_config,
                command,
                config,
                timeout,
            )

    def _ssh_execute_sync(
        self,
        host_config: HostConfig,
        command: str,
        config: FlowPilotConfig,
        timeout: int,
    ) -> tuple[int, str, str]:
        """同步执行 SSH 命令.

        Args:
            host_config: 主机配置
            command: 命令
            config: 配置对象
            timeout: 超时

        Returns:
            (exit_code, stdout, stderr)
        """
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # 处理跳板机
            sock = None
            if host_config.jump:
                jump_config = config.jumps.get(host_config.jump)
                if jump_config:
                    # 创建跳板机连接
                    jump_client = paramiko.SSHClient()
                    jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    jump_client.connect(
                        hostname=jump_config.addr,
                        port=jump_config.port,
                        username=jump_config.user,
                        timeout=timeout,
                    )

                    # 创建 tunnel
                    transport = jump_client.get_transport()
                    if transport:
                        sock = transport.open_channel(
                            "direct-tcpip",
                            (host_config.addr, host_config.port),
                            ("127.0.0.1", 0),
                        )

            # 连接目标主机
            connect_kwargs = {
                "hostname": host_config.addr,
                "port": host_config.port,
                "username": host_config.user,
                "timeout": timeout,
            }

            if sock:
                connect_kwargs["sock"] = sock

            if host_config.ssh_key:
                import os

                key_path = os.path.expanduser(host_config.ssh_key)
                connect_kwargs["key_filename"] = key_path

            client.connect(**connect_kwargs)

            # 执行命令
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)

            # 读取输出
            exit_code = stdout.channel.recv_exit_status()
            stdout_text = stdout.read().decode("utf-8", errors="replace")
            stderr_text = stderr.read().decode("utf-8", errors="replace")

            return exit_code, stdout_text, stderr_text

        finally:
            client.close()


class SSHExecBatchTool(MCPTool):
    """SSH 批量执行 Tool."""

    def __init__(self, policy_engine: PolicyEngine) -> None:
        """初始化批量 SSH Tool.

        Args:
            policy_engine: 策略引擎
        """
        self.policy_engine = policy_engine
        self.ssh_exec_tool = SSHExecTool(policy_engine)

    @property
    def name(self) -> str:
        """Tool 名称."""
        return "ssh_exec_batch"

    @property
    def description(self) -> str:
        """Tool 描述."""
        return "批量在多台主机执行相同命令"

    @property
    def input_schema(self) -> dict[str, Any]:
        """输入 Schema."""
        return {
            "type": "object",
            "properties": {
                "hosts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "主机别名列表",
                },
                "command": {
                    "type": "string",
                    "description": "要执行的命令",
                },
                "parallel": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否并发执行",
                },
                "continue_on_error": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否在错误时继续",
                },
                "_confirm_token": {
                    "type": "string",
                    "description": "确认 token",
                },
            },
            "required": ["hosts", "command"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """批量执行 SSH 命令.

        Args:
            hosts: 主机列表
            command: 命令
            parallel: 是否并发
            continue_on_error: 是否在错误时继续
            _confirm_token: 确认 token

        Returns:
            聚合的执行结果
        """
        hosts = kwargs["hosts"]
        command = kwargs["command"]
        parallel = kwargs.get("parallel", True)
        confirm_token = kwargs.get("_confirm_token")

        # 策略检查（批量操作）
        decision = self.policy_engine.check(
            tool_name=self.name,
            args={"hosts": hosts, "command": command},
        )

        if decision.effect == PolicyEffect.REQUIRE_CONFIRM:
            if not confirm_token or not self.policy_engine.validate_confirm_token(confirm_token):
                return ToolResult(
                    status=ToolStatus.PENDING_CONFIRM,
                    confirm_token=decision.confirm_token,
                    preview={
                        "host_count": len(hosts),
                        "hosts": hosts,
                        "command": command,
                        "message": decision.message,
                    },
                )
            self.policy_engine.consume_confirm_token(confirm_token)

        # 执行批量操作
        if parallel:
            results = await self._execute_parallel(hosts, command, confirm_token)
        else:
            results = await self._execute_sequential(hosts, command, confirm_token)

        # 聚合结果
        success_count = sum(1 for r in results if r.status == ToolStatus.SUCCESS)
        error_count = len(results) - success_count

        output_lines = []
        for host, result in zip(hosts, results):
            status_icon = "✅" if result.status == ToolStatus.SUCCESS else "❌"
            output_lines.append(f"{status_icon} {host}: {result.output or result.error}")

        return ToolResult(
            status=ToolStatus.SUCCESS if error_count == 0 else ToolStatus.ERROR,
            output="\n".join(output_lines),
            metadata={
                "total": len(hosts),
                "success": success_count,
                "error": error_count,
                "results": [
                    {"host": h, "status": r.status.value, "exit_code": r.exit_code}
                    for h, r in zip(hosts, results)
                ],
            },
        )

    async def _execute_parallel(
        self, hosts: list[str], command: str, confirm_token: str | None
    ) -> list[ToolResult]:
        """并发执行."""
        tasks = [
            self.ssh_exec_tool.execute(
                host=host, command=command, _confirm_token=confirm_token
            )
            for host in hosts
        ]
        return await asyncio.gather(*tasks)

    async def _execute_sequential(
        self, hosts: list[str], command: str, confirm_token: str | None
    ) -> list[ToolResult]:
        """顺序执行."""
        results = []
        for host in hosts:
            result = await self.ssh_exec_tool.execute(
                host=host, command=command, _confirm_token=confirm_token
            )
            results.append(result)
        return results
