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
    prompt: str = typer.Argument(None, help="自然语言请求（session 模式可省略）"),
    provider: str = typer.Option(None, "--provider", "-p", help="指定 LLM 提供商"),
    env: str = typer.Option(None, "--env", "-e", help="强制指定环境"),
    dry_run: bool = typer.Option(False, "--dry-run", help="仅生成 Plan，不执行"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认（仅非生产环境）"),
    session: bool = typer.Option(False, "--session", "-s", help="交互式会话模式"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON 格式"),
    verbose: bool = typer.Option(False, "--verbose", help="显示详细信息"),
) -> None:
    """执行自然语言请求.

    Examples:
        flowpilot chat "查看 prod-api-3 的运行时间"
        flowpilot chat "排查 payment 服务错误" --provider claude
        flowpilot chat "重启服务" -y  # 跳过确认
        flowpilot chat --session       # 交互式会话
        flowpilot chat "查看状态" --json  # JSON 输出
    """
    if session:
        asyncio.run(_session_mode(provider, env, dry_run, yes, json_output, verbose))
    elif prompt:
        asyncio.run(_chat_async(prompt, provider, env, dry_run, yes, json_output, verbose))
    else:
        console.print("[red]请提供请求内容或使用 --session 模式[/red]")


async def _chat_async(
    prompt: str,
    provider: str | None,
    env: str | None,
    dry_run: bool,
    yes: bool,
    json_output: bool,
    verbose: bool,
) -> dict | None:
    """异步执行 chat 命令.

    Returns:
        如果 json_output=True，返回结果字典
    """

    try:
        # 1. 加载配置
        loader = ConfigLoader()
        config = loader.load()

        # 2. 初始化组件
        policy_engine = PolicyEngine(config)
        audit_logger = AuditLogger()
        tool_registry = ToolRegistry()

        # 注册 SSH Tools
        ssh_tool = SSHExecTool(config, policy_engine)
        tool_registry.register(ssh_tool)
        tool_registry.register(SSHExecBatchTool(config, policy_engine))

        # 注册日志 Tools
        from flowpilot.tools.logs import DockerLogsTool, LogSearchTool, LogTailTool

        tool_registry.register(LogTailTool(ssh_tool))
        tool_registry.register(LogSearchTool(ssh_tool))
        tool_registry.register(DockerLogsTool(ssh_tool))

        # 注册 Git Tools
        from flowpilot.tools.git import GitDiffTool, GitLogTool, GitStatusTool

        tool_registry.register(GitStatusTool(ssh_tool))
        tool_registry.register(GitLogTool(ssh_tool))
        tool_registry.register(GitDiffTool(ssh_tool))

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


async def _session_mode(
    provider: str | None,
    env: str | None,
    dry_run: bool,
    yes: bool,
    json_output: bool,
    verbose: bool,
) -> None:
    """交互式会话模式."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory

    console.print("\n[bold cyan]🤖 FlowPilot 交互式会话[/bold cyan]")
    console.print("输入请求，按 Ctrl+D 或输入 'exit' 退出\n")

    prompt_session: PromptSession = PromptSession(history=InMemoryHistory())

    while True:
        try:
            user_input = await asyncio.to_thread(
                prompt_session.prompt,
                "flowpilot> ",
            )

            if not user_input.strip():
                continue

            if user_input.strip().lower() in ("exit", "quit", "q"):
                console.print("[dim]再见！[/dim]")
                break

            # 执行请求
            await _chat_async(
                user_input,
                provider,
                env,
                dry_run,
                yes,
                json_output,
                verbose,
            )
            console.print()  # 空行分隔

        except EOFError:
            console.print("\n[dim]再见！[/dim]")
            break
        except KeyboardInterrupt:
            console.print("\n[yellow]已中断[/yellow]")
            continue


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


@app.command(name="continue")
def continue_session(
    session_id: str = typer.Argument(None, help="会话 ID（可选，默认最近会话）"),
    provider: str = typer.Option(None, "--provider", "-p", help="指定 LLM 提供商"),
) -> None:
    """继续上次会话.

    Examples:
        flowpilot continue                      # 继续最近会话
        flowpilot continue sess_1768148771      # 指定会话
    """
    from flowpilot.audit.logger import AuditLogger

    audit_logger = AuditLogger()

    # 获取会话
    if session_id:
        session = audit_logger.get_session(session_id)
    else:
        # 获取最近的会话
        recent = audit_logger.get_recent_sessions(limit=1)
        if not recent:
            console.print("[yellow]没有可继续的会话[/yellow]")
            return
        session = recent[0]
        session_id = session["session_id"]

    if not session:
        console.print(f"[red]会话未找到: {session_id}[/red]")
        return

    # 显示会话信息
    console.print(f"\n[bold]📂 继续会话: {session_id}[/bold]")
    console.print(f"原始请求: {session.get('input', 'N/A')}")
    console.print(f"上次状态: {session.get('status', 'N/A')}\n")

    # 提示用户输入新请求
    try:
        from prompt_toolkit import prompt

        new_prompt = prompt("继续> ")
        if new_prompt.strip():
            # 调用 chat 命令
            asyncio.run(_chat_async(
                f"继续之前的任务。之前的请求是: {session.get('input', '')}。现在: {new_prompt}",
                provider,
                None,  # env
                False,  # dry_run
                False,  # yes
                False,  # verbose
            ))
    except KeyboardInterrupt:
        console.print("\n[yellow]已取消[/yellow]")

@app.command()
def report(
    session_id: str = typer.Argument(..., help="会话 ID"),
    format: str = typer.Option("markdown", "--format", "-f", help="输出格式: markdown | html"),
    output: str = typer.Option(None, "--output", "-o", help="输出到文件"),
) -> None:
    """生成会话报告.

    Examples:
        flowpilot report sess_123456                    # 显示 Markdown
        flowpilot report sess_123456 -f html -o r.html  # 导出 HTML
    """
    try:
        audit_logger = AuditLogger()
        reporter = ReportGenerator(audit_logger)

        report_content = reporter.generate_session_report(session_id, format=format)

        if output:
            from pathlib import Path

            Path(output).write_text(report_content, encoding="utf-8")
            console.print(f"[green]✅ 报告已保存到: {output}[/green]")
        elif format == "html":
            console.print("[yellow]HTML 格式请使用 -o 参数保存到文件[/yellow]")
            console.print(report_content[:500] + "...")
        else:
            console.print(Markdown(report_content))

    except Exception as e:
        console.print(f"[red]❌ 生成报告失败: {e}[/red]")


@app.command()
def stats(
    since: str = typer.Option("7d", "--since", "-s", help="时间范围: 1d, 7d, 30d"),
) -> None:
    """查看使用统计.

    Examples:
        flowpilot stats              # 最近 7 天
        flowpilot stats --since 30d  # 最近 30 天
    """
    try:
        audit_logger = AuditLogger()
        reporter = ReportGenerator(audit_logger)

        stats = reporter.generate_statistics(since=since)

        console.print(f"\n[bold]📊 FlowPilot 使用统计（最近 {stats['period']}）[/bold]\n")
        console.print(f"  总会话数: [bold]{stats['total']}[/bold]")
        console.print(f"  成功: [green]{stats['success']}[/green]")
        console.print(f"  失败: [red]{stats['error']}[/red]")
        console.print(f"  成功率: [bold]{stats['success_rate']}%[/bold]\n")

        if stats.get("top_tools"):
            console.print("[bold]🔧 最常用工具:[/bold]")
            for name, count in stats["top_tools"]:
                console.print(f"  • {name}: {count} 次")

    except Exception as e:
        console.print(f"[red]❌ 获取统计失败: {e}[/red]")


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


@app.command()
def alias(
    action: str = typer.Argument("list", help="操作: list | add | remove"),
    name: str = typer.Argument(None, help="别名名称"),
    command: str = typer.Argument(None, help="完整命令（add 时需要）"),
) -> None:
    """管理命令别名.

    Examples:
        flowpilot alias                     # 列出所有别名
        flowpilot alias list                # 列出所有别名
        flowpilot alias add mylog "查看nginx日志"  # 添加别名
        flowpilot alias remove mylog        # 移除别名
    """
    from flowpilot.cli.aliases import AliasManager

    manager = AliasManager()

    if action == "list":
        all_aliases = manager.list_all()

        console.print("\n[bold]📝 内置别名:[/bold]")
        for alias_name, cmd in all_aliases["builtin"].items():
            console.print(f"  [cyan]{alias_name}[/cyan] → {cmd}")

        if all_aliases["user"]:
            console.print("\n[bold]👤 用户别名:[/bold]")
            for alias_name, cmd in all_aliases["user"].items():
                console.print(f"  [green]{alias_name}[/green] → {cmd}")
        else:
            console.print("\n[dim]暂无用户自定义别名[/dim]")

    elif action == "add":
        if not name or not command:
            console.print("[red]用法: flowpilot alias add <名称> <命令>[/red]")
            return
        manager.add(name, command)
        console.print(f"[green]✅ 已添加别名: {name} → {command}[/green]")

    elif action == "remove":
        if not name:
            console.print("[red]用法: flowpilot alias remove <名称>[/red]")
            return
        if manager.remove(name):
            console.print(f"[green]✅ 已移除别名: {name}[/green]")
        else:
            console.print(f"[yellow]别名不存在: {name}[/yellow]")

    else:
        console.print(f"[red]未知操作: {action}[/red]")


@app.command()
def hosts(
    group: str = typer.Option(None, "--group", "-g", help="按分组过滤"),
    env: str = typer.Option(None, "--env", "-e", help="按环境过滤"),
) -> None:
    """列出所有主机（支持分组和过滤）.

    Examples:
        flowpilot hosts                 # 列出所有主机
        flowpilot hosts -g 生产服务器    # 按分组筛选
        flowpilot hosts -e prod         # 按环境筛选
    """
    try:
        loader = ConfigLoader()
        config = loader.load()

        if not config.hosts:
            console.print("[yellow]未配置任何主机[/yellow]")
            return

        # 按分组组织
        grouped: dict[str, list[tuple[str, Any]]] = {}
        for name, host in config.hosts.items():
            # 应用过滤
            if group and host.group != group:
                continue
            if env and host.env != env:
                continue

            g = host.group or "default"
            if g not in grouped:
                grouped[g] = []
            grouped[g].append((name, host))

        if not grouped:
            console.print("[yellow]无匹配的主机[/yellow]")
            return

        console.print("\n[bold]📡 主机列表[/bold]\n")

        for grp, hosts_list in sorted(grouped.items()):
            console.print(f"[bold cyan]【{grp}】[/bold cyan]")
            for name, host in hosts_list:
                env_color = {"prod": "red", "staging": "yellow", "dev": "green"}.get(host.env, "white")
                desc = f" - {host.description}" if host.description else ""
                console.print(f"  [{env_color}]{host.env}[/{env_color}] {name}: {host.user}@{host.addr}{desc}")
            console.print()

    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
    except Exception as e:
        console.print(f"[red]❌ 加载配置失败: {e}[/red]")


@app.command()
def exec(
    host: str = typer.Argument(..., help="主机别名或 @group（批量）"),
    command: str = typer.Argument(..., help="要执行的命令"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
) -> None:
    """快捷执行命令（绕过 LLM）.

    Examples:
        flowpilot exec ubuntu "uptime"           # 单机执行
        flowpilot exec ubuntu "df -h" -y         # 跳过确认
        flowpilot exec @生产服务器 "uptime"       # 分组批量执行
    """
    asyncio.run(_exec_async(host, command, yes))


async def _exec_async(host: str, command: str, yes: bool) -> None:
    """执行快捷命令."""
    try:
        loader = ConfigLoader()
        config = loader.load()
        policy_engine = PolicyEngine(config)

        from flowpilot.tools.ssh import SSHExecTool, SSHExecBatchTool

        ssh_tool = SSHExecTool(config, policy_engine)

        # 检查是否是分组批量执行
        if host.startswith("@"):
            group_name = host[1:]
            target_hosts = [
                name for name, h in config.hosts.items()
                if h.group == group_name
            ]
            if not target_hosts:
                console.print(f"[red]分组 '{group_name}' 中没有主机[/red]")
                return

            console.print(f"[bold]⚡ 批量执行: {len(target_hosts)} 台主机[/bold]")
            for h in target_hosts:
                console.print(f"  - {h}")

            if not yes:
                import typer
                if not typer.confirm("确认执行?"):
                    console.print("[yellow]已取消[/yellow]")
                    return

            # 批量执行
            batch_tool = SSHExecBatchTool(config, policy_engine)
            result = await batch_tool.execute(hosts=target_hosts, command=command)
            console.print(f"\n{result.output}")

        else:
            # 单机执行
            console.print(f"[bold]⚡ 执行: {host}[/bold]")
            console.print(f"[dim]$ {command}[/dim]\n")

            result = await ssh_tool.execute(host=host, command=command, _confirm_token="auto" if yes else None)

            if result.status.value == "success":
                console.print(result.output)
            elif result.status.value == "pending_confirm":
                console.print("[yellow]需要确认，请使用 -y 参数跳过[/yellow]")
            else:
                console.print(f"[red]❌ {result.error}[/red]")

    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
    except Exception as e:
        console.print(f"[red]❌ 执行失败: {e}[/red]")


if __name__ == "__main__":
    app()
