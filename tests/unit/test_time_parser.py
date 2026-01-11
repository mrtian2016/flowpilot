"""时间解析工具测试."""

from datetime import datetime, timedelta

import pytest

from flowpilot.utils.time_parser import (
    TimeParseError,
    format_duration,
    parse_absolute_time,
    parse_time,
    parse_time_window,
)


def test_parse_time_window_minutes():
    """测试分钟解析."""
    assert parse_time_window("10m") == timedelta(minutes=10)
    assert parse_time_window("30M") == timedelta(minutes=30)  # 大小写不敏感


def test_parse_time_window_hours():
    """测试小时解析."""
    assert parse_time_window("1h") == timedelta(hours=1)
    assert parse_time_window("24h") == timedelta(hours=24)


def test_parse_time_window_days():
    """测试天数解析."""
    assert parse_time_window("1d") == timedelta(days=1)
    assert parse_time_window("7d") == timedelta(days=7)


def test_parse_time_window_weeks():
    """测试周解析."""
    assert parse_time_window("1w") == timedelta(weeks=1)
    assert parse_time_window("2w") == timedelta(weeks=2)


def test_parse_time_window_seconds():
    """测试秒解析."""
    assert parse_time_window("30s") == timedelta(seconds=30)


def test_parse_time_window_invalid():
    """测试无效格式."""
    with pytest.raises(TimeParseError) as exc_info:
        parse_time_window("invalid")
    assert "无效的时间窗格式" in str(exc_info.value)

    with pytest.raises(TimeParseError):
        parse_time_window("10x")  # 无效单位

    with pytest.raises(TimeParseError):
        parse_time_window("abc")


def test_parse_absolute_time_iso():
    """测试 ISO 8601 格式."""
    result = parse_absolute_time("2024-01-09T10:30:00")
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 9
    assert result.hour == 10
    assert result.minute == 30


def test_parse_absolute_time_common_formats():
    """测试常见格式."""
    # 日期 + 时间
    result1 = parse_absolute_time("2024-01-09 10:30:00")
    assert result1.year == 2024

    # 日期 + 时间（斜杠分隔）
    result2 = parse_absolute_time("2024/01/09 10:30")
    assert result2.month == 1


def test_parse_absolute_time_invalid():
    """测试无效格式."""
    with pytest.raises(TimeParseError):
        parse_absolute_time("not a date")

    with pytest.raises(TimeParseError):
        parse_absolute_time("2024-13-45")  # 无效的月/日


def test_parse_time_relative():
    """测试统一解析（相对时间）."""
    before = datetime.now()
    result = parse_time("10m")
    after = datetime.now()

    # 结果应该是大约 10 分钟前
    expected = datetime.now() - timedelta(minutes=10)
    assert abs((result - expected).total_seconds()) < 2  # 允许 2 秒误差


def test_parse_time_absolute():
    """测试统一解析（绝对时间）."""
    result = parse_time("2024-01-09T10:30:00")
    assert result.year == 2024
    assert result.month == 1


def test_format_duration_seconds():
    """测试秒级时长格式化."""
    assert format_duration(0.5) == "0.50s"
    assert format_duration(2.3) == "2.3s"
    assert format_duration(45) == "45.0s"


def test_format_duration_minutes():
    """测试分钟级时长格式化."""
    assert format_duration(90) == "1m 30s"
    assert format_duration(120) == "2m"
    assert format_duration(65) == "1m 5s"


def test_format_duration_hours():
    """测试小时级时长格式化."""
    assert format_duration(3600) == "1h"
    assert format_duration(3660) == "1h 1m"
    assert format_duration(7325) == "2h 2m"
