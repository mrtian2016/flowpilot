"""FlowPilot CLI 入口."""

import asyncio
import os
import secrets
import shutil
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm

from flowpilot import __version__
from flowpilot.agent.conversation import Conversation
from flowpilot.agent.executor import ToolExecutor
from flowpilot.agent.router import ProviderRouter
from flowpilot.audit.logger import AuditLogger
from flowpilot.audit.reporter import ReportGenerator
from flowpilot.config.loader import ConfigLoader
from flowpilot.policy.engine import PolicyEngine
from flowpilot.tools.base import ToolRegistry
from flowpilot.tools.ssh import SSHExecBatchTool, SSHExecTool

app = typer.Typer(
    name="flowpilot",
    help="AI Agent for programmer workflow automation",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """显示版本信息."""
    if value:
        console.print(f"FlowPilot version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="显示版本信息",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """FlowPilot - AI Agent for programmer workflow automation."""
    pass


@app.command()
def init() -> None:
    """初始化 FlowPilot 配置."""
    console.print("[bold green]初始化 FlowPilot 配置...[/bold green]")

    config_dir = Path.home() / ".flowpilot"
    config_file = config_dir / "config.yaml"

    # 创建配置目录
    if not config_dir.exists():
        config_dir.mkdir(parents=True)
        console.print(f"✅ 创建配置目录: {config_dir}")

    # 复制配置模板
    if config_file.exists():
        overwrite = Confirm.ask(f"配置文件已存在: {config_file}，是否覆盖？")
        if not overwrite:
            console.print("❌ 取消初始化")
            return

    # 查找示例配置文件
    example_config = Path(__file__).parent.parent.parent.parent / "config.example.yaml"
    if example_config.exists():
        shutil.copy(example_config, config_file)
        console.print(f"✅ 创建配置文件: {config_file}")
    else:
        console.print(f"⚠️  示例配置文件未找到: {example_config}")
        console.print(f"请手动创建配置文件: {config_file}")

    # 提示配置 API Keys
    console.print("\n[bold yellow]⚠️  请配置 API Keys：[/bold yellow]")
    console.print("在 ~/.bashrc 或 ~/.zshrc 中添加：")
    console.print("  export ANTHROPIC_API_KEY=sk-ant-...")
    console.print("  export GOOGLE_API_KEY=AIza...")
    console.print("  export ZHIPU_API_KEY=...")

    console.print("\n[bold green]✅ 初始化完成！[/bold green]")
    console.print(f"配置文件: {config_file}")
    console.print("编辑配置后运行: flowpilot config validate")


@app.command()
def chat(
    prompt: str = typer.Argument(..., help="自然语言请求"),
    provider: str = typer.Option(None, "--provider", "-p", help="指定 LLM 提供商"),
    env: str = typer.Option(None, "--env", "-e", help="强制指定环境"),
    dry_run: bool = typer.Option(False, "--dry-run", help="仅生成 Plan，不执行"),
    verbose: bool = typer.Option(False, "--verbose", help="显示详细信息"),
) -> None:
    """执行自然语言请求.

    Examples:
        flowpilot chat "查看 prod-api-3 的运行时间"
        flowpilot chat "排查 payment 服务错误" --provider claude
    """
    asyncio.run(_chat_async(prompt, provider, env, dry_run, verbose))


async def _chat_async(
    prompt: str,
    provider: str | None,
    env: str | None,
    dry_run: bool,
    verbose: bool,
) -> None:
    """异步执行 chat 命令."""
    try:
        # 1. 加载配置
        loader = ConfigLoader()
        config = loader.load()

        # 2. 初始化组件
        policy_engine = PolicyEngine(config)
        audit_logger = AuditLogger()
        tool_registry = ToolRegistry()

        # 注册 Tools
        tool_registry.register(SSHExecTool(config, policy_engine))
        tool_registry.register(SSHExecBatchTool(config, policy_engine))

        # 3. 初始化 Agent
        router = ProviderRouter(config.llm)
        llm_provider = router.get_provider(provider_name=provider)

        # 4. 创建会话
        session_id = f"sess_{int(time.time())}_{secrets.token_hex(4)}"
        conversation = Conversation()
        tool_executor = ToolExecutor(tool_registry, audit_logger)

        # 记录会话
        audit_logger.create_session(session_id, prompt)

        console.print(f"\n[bold]🤖 FlowPilot ({llm_provider.name})[/bold]")
        console.print(f"[dim]Session: {session_id}[/dim]\n")

        # 5. Agent 循环
        conversation.add_user_message(prompt)

        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            if verbose:
                console.print(f"[dim]--- Iteration {iteration} ---[/dim]")

            # 调用 LLM
            console.print("[dim]正在思考...[/dim]")
            tools_def = tool_registry.get_mcp_definitions()

            response = await llm_provider.chat(
                messages=conversation.get_messages(),
                tools=tools_def if not dry_run else None,
            )

            if verbose:
                console.print(f"[dim]LLM 响应: {response['stop_reason']}[/dim]")

            # 处理响应
            if response["content"]:
                console.print(Panel(response["content"], title="Agent"))

            # 检查是否有 Tool 调用
            if not response["tool_calls"]:
                # 没有 Tool 调用，结束
                audit_logger.update_session(
                    session_id=session_id,
                    final_output=response["content"],
                    status="completed",
                    provider=llm_provider.name,
                )
                break

            # 执行 Tools
            console.print(f"\n[bold yellow]🔧 执行 {len(response['tool_calls'])} 个工具...[/bold yellow]")

            for tool_call in response["tool_calls"]:
                console.print(f"  - {tool_call['name']}")

            if dry_run:
                console.print("[yellow]Dry-run 模式，跳过实际执行[/yellow]")
                break

            # 执行 Tool 调用
            tool_results = await tool_executor.execute_tool_calls(
                response["tool_calls"], session_id
            )

            # 处理 Tool 结果
            for result in tool_results:
                if result.get("error"):
                    console.print(f"[red]❌ 错误: {result['error']}[/red]")
                else:
                    console.print(f"[green]✅ {result['content'][:200]}...[/green]")

                # 将结果添加到会话
                conversation.add_tool_result(
                    result["tool_use_id"],
                    result.get("content", result.get("error", "")),
                )

            # 继续循环

        if iteration >= max_iterations:
            console.print("[yellow]⚠️  达到最大迭代次数[/yellow]")

        console.print(f"\n[dim]Session完成: {session_id}[/dim]")

    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
    except ValueError as e:
        console.print(f"[red]❌ {e}[/red]")
    except Exception as e:
        console.print(f"[red]❌ 执行失败: {e}[/red]")
        if verbose:
            import traceback

            traceback.print_exc()


@app.command()
def history(
    last: int = typer.Option(10, "--last", "-n", help="显示最近 N 条记录"),
    env: str = typer.Option(None, "--env", help="按环境过滤"),
) -> None:
    """查看执行历史."""
    try:
        audit_logger = AuditLogger()
        sessions = audit_logger.get_recent_sessions(limit=last, env=env)

        if not sessions:
            console.print("[yellow]没有执行记录[/yellow]")
            return

        console.print(f"\n[bold]📋 最近 {len(sessions)} 条执行记录[/bold]\n")

        for sess in sessions:
            status_icon = "✅" if sess["status"] == "completed" else "❌"
            timestamp = sess["timestamp"][:19] if sess["timestamp"] else "N/A"
            duration = f"{sess['duration_sec']:.1f}s" if sess['duration_sec'] else "N/A"

            console.print(f"{status_icon} [{timestamp}] {sess['user']}")
            console.print(f"   {sess['input'][:80]}...")
            console.print(f"   [dim]耗时: {duration}, ID: {sess['session_id']}[/dim]\n")

    except Exception as e:
        console.print(f"[red]❌ 查询失败: {e}[/red]")


@app.command()
def report(
    session_id: str = typer.Argument(..., help="会话 ID"),
) -> None:
    """生成会话报告."""
    try:
        audit_logger = AuditLogger()
        reporter = ReportGenerator(audit_logger)

        markdown_report = reporter.generate_session_report(session_id)

        console.print(Markdown(markdown_report))

    except Exception as e:
        console.print(f"[red]❌ 生成报告失败: {e}[/red]")


@app.command()
def config(
    subcommand: str = typer.Argument("show", help="子命令: show | validate | edit"),
) -> None:
    """管理配置.

    Examples:
        flowpilot config show
        flowpilot config validate
    """
    if subcommand == "show":
        _config_show()
    elif subcommand == "validate":
        _config_validate()
    elif subcommand == "edit":
        _config_edit()
    else:
        console.print(f"[red]❌ 未知子命令: {subcommand}[/red]")
        console.print("可用命令: show, validate, edit")


def _config_show() -> None:
    """显示配置."""
    try:
        loader = ConfigLoader()
        config_path = loader.config_path

        if not config_path.exists():
            console.print(f"[red]❌ 配置文件不存在: {config_path}[/red]")
            return

        with open(config_path, encoding="utf-8") as f:
            content = f.read()

        console.print(f"\n[bold]配置文件: {config_path}[/bold]\n")
        console.print(content)

    except Exception as e:
        console.print(f"[red]❌ 读取配置失败: {e}[/red]")


def _config_validate() -> None:
    """校验配置."""
    try:
        loader = ConfigLoader()
        is_valid, message = loader.validate()

        if is_valid:
            console.print(f"[green]{message}[/green]")
        else:
            console.print(f"[red]{message}[/red]")

    except Exception as e:
        console.print(f"[red]❌ 校验失败: {e}[/red]")


def _config_edit() -> None:
    """编辑配置."""
    loader = ConfigLoader()
    config_path = loader.config_path

    editor = os.getenv("EDITOR", "vim")
    os.system(f"{editor} {config_path}")


@app.command(name="import-hosts")
def import_hosts(
    ssh_config: str = typer.Option(
        "~/.ssh/config",
        "--ssh-config",
        "-s",
        help="SSH 配置文件路径",
    ),
    env: str = typer.Option(
        "dev",
        "--env",
        "-e",
        help="默认环境标签",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="输出到文件（默认输出到终端）",
    ),
    append: bool = typer.Option(
        False,
        "--append",
        "-a",
        help="追加到现有配置文件",
    ),
) -> None:
    """从 SSH 配置文件导入主机到 FlowPilot.

    示例：
        flowpilot import-hosts                     # 预览导入内容
        flowpilot import-hosts -o hosts.yaml      # 输出到文件
        flowpilot import-hosts --append           # 追加到现有配置
    """
    from pathlib import Path

    from flowpilot.config.ssh_importer import (
        convert_to_flowpilot_hosts,
        format_hosts_yaml,
        parse_ssh_config,
    )

    # 解析 SSH 配置
    ssh_path = Path(ssh_config).expanduser()
    console.print(f"[bold]解析 SSH 配置: {ssh_path}[/bold]\n")

    ssh_hosts = parse_ssh_config(ssh_path)

    if not ssh_hosts:
        console.print("[yellow]未找到可导入的主机配置[/yellow]")
        return

    console.print(f"[green]找到 {len(ssh_hosts)} 个主机:[/green]")
    for host in ssh_hosts:
        console.print(f"  • {host['name']} → {host.get('hostname', 'N/A')}:{host.get('port', 22)}")

    # 转换为 FlowPilot 格式
    flowpilot_hosts = convert_to_flowpilot_hosts(ssh_hosts, default_env=env)
    yaml_content = format_hosts_yaml(flowpilot_hosts)

    # 输出
    if append:
        # 追加到现有配置
        config_path = Path.home() / ".flowpilot" / "config.yaml"
        if not config_path.exists():
            console.print(f"[red]❌ 配置文件不存在: {config_path}[/red]")
            console.print("请先运行: flowpilot init")
            return

        console.print(f"\n[bold yellow]⚠️  将追加到: {config_path}[/bold yellow]")
        confirm = typer.confirm("确认追加？")
        if not confirm:
            console.print("[yellow]取消操作[/yellow]")
            return

        with open(config_path, "a", encoding="utf-8") as f:
            f.write("\n# 从 SSH 配置导入的主机\n")
            f.write(yaml_content)

        console.print(f"[green]✅ 已追加到: {config_path}[/green]")

    elif output:
        # 输出到文件
        output_path = Path(output).expanduser()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        console.print(f"\n[green]✅ 已保存到: {output_path}[/green]")

    else:
        # 预览输出
        console.print("\n[bold]FlowPilot 格式配置（预览）:[/bold]\n")
        console.print(yaml_content)
        console.print("[dim]使用 --output 或 --append 保存配置[/dim]")


if __name__ == "__main__":
    app()
