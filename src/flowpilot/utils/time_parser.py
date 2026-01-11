"""时间窗解析工具."""

import re
from datetime import datetime, timedelta

from dateutil import parser as dateutil_parser


class TimeParseError(ValueError):
    """时间解析错误."""

    pass


def parse_time_window(time_str: str) -> timedelta:
    """解析相对时间窗（如 10m, 1h, 2d）.

    Args:
        time_str: 时间字符串，支持格式：
            - 10m, 30m (分钟)
            - 1h, 2h (小时)
            - 1d, 7d (天)
            - 1w (周)

    Returns:
        时间差对象

    Raises:
        TimeParseError: 格式错误
    """
    pattern = r"^(\d+)([smhdw])$"
    match = re.match(pattern, time_str.lower().strip())

    if not match:
        raise TimeParseError(
            f"无效的时间窗格式: {time_str}\n" f"支持格式: 10m(分钟), 1h(小时), 2d(天), 1w(周)"
        )

    value = int(match.group(1))
    unit = match.group(2)

    # 单位映射
    unit_map = {
        "s": timedelta(seconds=value),
        "m": timedelta(minutes=value),
        "h": timedelta(hours=value),
        "d": timedelta(days=value),
        "w": timedelta(weeks=value),
    }

    return unit_map[unit]


def parse_absolute_time(time_str: str) -> datetime:
    """解析绝对时间（ISO 8601 或常见格式）.

    Args:
        time_str: 时间字符串，如：
            - 2024-01-09T10:30:00
            - 2024-01-09 10:30:00
            - 2024/01/09 10:30

    Returns:
        datetime 对象

    Raises:
        TimeParseError: 解析失败
    """
    try:
        return dateutil_parser.parse(time_str)
    except (ValueError, TypeError) as e:
        raise TimeParseError(f"无效的时间格式: {time_str}") from e


def parse_time(time_str: str) -> datetime:
    """统一时间解析（自动识别相对时间或绝对时间）.

    Args:
        time_str: 时间字符串

    Returns:
        datetime 对象（相对时间转换为绝对时间）

    Raises:
        TimeParseError: 解析失败
    """
    # 尝试解析相对时间
    try:
        delta = parse_time_window(time_str)
        return datetime.now() - delta  # 相对时间表示"多久之前"
    except TimeParseError:
        pass

    # 尝试解析绝对时间
    return parse_absolute_time(time_str)


def format_duration(seconds: float) -> str:
    """格式化时长为人类可读格式.

    Args:
        seconds: 秒数

    Returns:
        格式化的时长字符串，如 "2.5s", "1m 30s", "1h 5m"
    """
    if seconds < 1:
        return f"{seconds:.2f}s"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
