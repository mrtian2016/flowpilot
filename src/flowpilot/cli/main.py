"""FlowPilot CLI 入口."""

import typer
from rich.console import Console

from flowpilot import __version__

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
    console.print("功能开发中...")


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
    console.print(f"[bold]处理请求:[/bold] {prompt}")
    console.print("功能开发中...")


@app.command()
def history(
    last: int = typer.Option(10, "--last", "-n", help="显示最近 N 条记录"),
    env: str = typer.Option(None, "--env", help="按环境过滤"),
) -> None:
    """查看执行历史."""
    console.print(f"[bold]最近 {last} 条执行记录:[/bold]")
    console.print("功能开发中...")


@app.command()
def config(
    subcommand: str = typer.Argument("show", help="子命令: show | validate | edit"),
) -> None:
    """管理配置.

    Examples:
        flowpilot config show
        flowpilot config validate
    """
    console.print(f"[bold]配置管理:[/bold] {subcommand}")
    console.print("功能开发中...")


if __name__ == "__main__":
    app()
