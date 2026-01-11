"""FlowPilot 统一日志模块."""

import logging
import os
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# 默认日志格式
DEFAULT_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
SIMPLE_FORMAT = "%(message)s"

# 全局 logger 实例
_loggers: dict[str, logging.Logger] = {}


def get_logger(
    name: str = "flowpilot",
    level: str | None = None,
    log_file: str | Path | None = None,
    use_rich: bool = True,
) -> logging.Logger:
    """获取 logger 实例.

    Args:
        name: logger 名称
        level: 日志级别（默认从环境变量或 INFO）
        log_file: 日志文件路径（可选）
        use_rich: 是否使用 Rich 格式化输出

    Returns:
        配置好的 logger 实例
    """
    # 检查缓存
    if name in _loggers:
        return _loggers[name]

    # 确定日志级别
    if level is None:
        level = os.getenv("FLOWPILOT_LOG_LEVEL", "INFO")
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)

    # 创建 logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    logger.handlers = []  # 清除已有 handlers

    # 控制台 handler
    if use_rich:
        console_handler = RichHandler(
            console=Console(stderr=True),
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
        )
        console_handler.setFormatter(logging.Formatter(SIMPLE_FORMAT))
    else:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))

    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)

    # 文件 handler（可选）
    if log_file:
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
        file_handler.setLevel(log_level)
        logger.addHandler(file_handler)

    # 缓存
    _loggers[name] = logger
    return logger


def log_tool_call(
    logger: logging.Logger,
    tool_name: str,
    args: dict[str, Any],
    result: Any = None,
    error: Exception | None = None,
    duration_sec: float | None = None,
) -> None:
    """记录 Tool 调用日志.

    Args:
        logger: logger 实例
        tool_name: Tool 名称
        args: 调用参数
        result: 执行结果（可选）
        error: 异常（可选）
        duration_sec: 执行时长（可选）
    """
    # 构建基本信息
    msg_parts = [f"Tool: {tool_name}"]

    if duration_sec is not None:
        msg_parts.append(f"Duration: {duration_sec:.2f}s")

    if error:
        logger.error(
            " | ".join(msg_parts) + f" | Error: {error}",
            exc_info=True,
        )
    else:
        logger.info(" | ".join(msg_parts))
        if result and logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Result: {result}")


def log_llm_call(
    logger: logging.Logger,
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    duration_sec: float | None = None,
    error: Exception | None = None,
) -> None:
    """记录 LLM 调用日志.

    Args:
        logger: logger 实例
        provider: Provider 名称
        model: 模型名称
        input_tokens: 输入 token 数
        output_tokens: 输出 token 数
        duration_sec: 执行时长
        error: 异常（可选）
    """
    msg_parts = [
        f"LLM: {provider}/{model}",
        f"Tokens: {input_tokens} → {output_tokens}",
    ]

    if duration_sec is not None:
        msg_parts.append(f"Duration: {duration_sec:.2f}s")

    if error:
        logger.error(" | ".join(msg_parts) + f" | Error: {error}")
    else:
        logger.info(" | ".join(msg_parts))


def log_policy_check(
    logger: logging.Logger,
    tool_name: str,
    effect: str,
    rule: str | None = None,
    message: str | None = None,
) -> None:
    """记录策略检查日志.

    Args:
        logger: logger 实例
        tool_name: Tool 名称
        effect: 策略效果（allow/require_confirm/deny）
        rule: 触发的规则名称
        message: 消息
    """
    msg = f"Policy: {tool_name} → {effect}"
    if rule:
        msg += f" (rule: {rule})"

    if effect == "deny":
        logger.warning(msg)
    elif effect == "require_confirm":
        logger.info(msg)
    else:
        logger.debug(msg)


# 预创建主 logger
main_logger = get_logger("flowpilot")
