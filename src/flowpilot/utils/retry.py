"""错误处理和重试机制."""

import asyncio
import functools
import random
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class RetryConfig:
    """重试配置."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ) -> None:
        """初始化重试配置.

        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟（秒）
            max_delay: 最大延迟（秒）
            exponential_base: 指数退避基数
            jitter: 是否添加随机抖动
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


# 默认重试配置
DEFAULT_RETRY_CONFIG = RetryConfig()


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """计算重试延迟.

    Args:
        attempt: 当前尝试次数（从 0 开始）
        config: 重试配置

    Returns:
        延迟秒数
    """
    delay = config.base_delay * (config.exponential_base**attempt)
    delay = min(delay, config.max_delay)

    if config.jitter:
        # 添加 ±25% 的随机抖动
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0, delay)


# 可重试的异常类型
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
)


class RetryableError(Exception):
    """可重试的错误."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


class RateLimitError(RetryableError):
    """API 限流错误."""

    def __init__(
        self,
        message: str = "API 限流",
        retry_after: float | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, original_error)
        self.retry_after = retry_after


class APIError(Exception):
    """API 错误."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        provider: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider = provider
        self.original_error = original_error


def retry_async(
    config: RetryConfig | None = None,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """异步重试装饰器.

    Args:
        config: 重试配置
        retryable_exceptions: 可重试的异常类型

    Returns:
        装饰器函数
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG

    if retryable_exceptions is None:
        retryable_exceptions = RETRYABLE_EXCEPTIONS + (RetryableError,)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except retryable_exceptions as e:
                    last_exception = e

                    # 检查是否已达最大重试次数
                    if attempt >= config.max_retries:
                        break

                    # 计算延迟
                    delay = calculate_delay(attempt, config)

                    # RateLimitError 可能有特定的 retry_after
                    if isinstance(e, RateLimitError) and e.retry_after:
                        delay = e.retry_after

                    # 等待后重试
                    await asyncio.sleep(delay)

            # 超过重试次数，抛出最后的异常
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry failed without exception")

        return wrapper

    return decorator


def is_rate_limit_error(error: Exception) -> bool:
    """判断是否为限流错误.

    Args:
        error: 异常

    Returns:
        是否为限流错误
    """
    if isinstance(error, RateLimitError):
        return True

    # 检查常见的限流错误模式
    error_str = str(error).lower()
    rate_limit_keywords = ["rate limit", "too many requests", "429", "quota exceeded"]

    return any(keyword in error_str for keyword in rate_limit_keywords)


def wrap_api_error(
    error: Exception,
    provider: str,
    operation: str = "api_call",
) -> APIError:
    """包装 API 错误.

    Args:
        error: 原始异常
        provider: Provider 名称
        operation: 操作名称

    Returns:
        APIError 实例
    """
    # 尝试提取状态码
    status_code = None
    if hasattr(error, "status_code"):
        status_code = error.status_code
    elif hasattr(error, "status"):
        status_code = error.status

    # 构建消息
    message = f"{provider} {operation} 失败: {error}"

    return APIError(
        message=message,
        status_code=status_code,
        provider=provider,
        original_error=error,
    )
