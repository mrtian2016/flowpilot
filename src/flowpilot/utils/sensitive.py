"""敏感信息脱敏工具."""

import re

# 敏感信息匹配模式
SENSITIVE_PATTERNS = [
    # Token 类
    (r'token["\s:=]+([a-zA-Z0-9_\-\.]{8,})', r"token=***MASKED***"),
    (r"Bearer\s+([a-zA-Z0-9_\-\.]+)", r"Bearer ***MASKED***"),
    # Password 类
    (r'password["\s:=]+([^\s"]{3,})', r"password=***MASKED***"),
    (r'passwd["\s:=]+([^\s"]{3,})', r"passwd=***MASKED***"),
    # Secret 类
    (r'secret["\s:=]+([^\s"]{3,})', r"secret=***MASKED***"),
    (r'api[_-]?key["\s:=]+([^\s"]{8,})', r"api_key=***MASKED***"),
    # Authorization Header
    (r"Authorization:\s*([^\n]+)", r"Authorization: ***MASKED***"),
    # AWS 风格
    (r"aws_secret_access_key[=\s]+([^\s]+)", r"aws_secret_access_key=***MASKED***"),
    (r"aws_access_key_id[=\s]+([^\s]+)", r"aws_access_key_id=***MASKED***"),
    # SSH 私钥
    (r"-----BEGIN.*PRIVATE KEY-----.*?-----END.*PRIVATE KEY-----", r"***SSH_PRIVATE_KEY_MASKED***"),
    # 常见密钥格式（sk-xxx, AIza-xxx 等）
    (r"\bsk-[a-zA-Z0-9]{20,}\b", r"***MASKED***"),
    (r"\bAIza[a-zA-Z0-9_-]{20,}\b", r"***MASKED***"),
]


def mask_sensitive(text: str) -> str:
    """脱敏敏感信息.

    Args:
        text: 原始文本

    Returns:
        脱敏后的文本
    """
    if not text:
        return text

    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE | re.DOTALL)

    return result


def is_sensitive(text: str) -> bool:
    """判断文本是否包含敏感信息.

    Args:
        text: 待检查的文本

    Returns:
        是否包含敏感信息
    """
    if not text:
        return False

    for pattern, _ in SENSITIVE_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            return True

    return False


def mask_dict(data: dict, keys_to_mask: list[str] | None = None) -> dict:
    """脱敏字典中的敏感字段.

    Args:
        data: 原始字典
        keys_to_mask: 需要脱敏的键名列表（默认常见敏感字段）

    Returns:
        脱敏后的字典（新副本）
    """
    if keys_to_mask is None:
        keys_to_mask = [
            "password",
            "passwd",
            "secret",
            "token",
            "api_key",
            "apikey",
            "access_key",
            "private_key",
            "ssh_key",
        ]

    result = {}
    for key, value in data.items():
        # 检查键名是否需要脱敏
        if any(sensitive_key in key.lower() for sensitive_key in keys_to_mask):
            result[key] = "***MASKED***"
        elif isinstance(value, str):
            # 对字符串值进行内容检查
            result[key] = mask_sensitive(value)
        elif isinstance(value, dict):
            # 递归处理嵌套字典
            result[key] = mask_dict(value, keys_to_mask)
        elif isinstance(value, list):
            # 处理列表
            result[key] = [
                mask_dict(item, keys_to_mask) if isinstance(item, dict) else mask_sensitive(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            result[key] = value

    return result
