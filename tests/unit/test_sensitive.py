"""脱敏工具测试."""

import pytest

from flowpilot.utils.sensitive import is_sensitive, mask_dict, mask_sensitive


def test_mask_token():
    """测试 token 脱敏."""
    text = 'Authorization: Bearer sk-ant-1234567890abcdef'
    result = mask_sensitive(text)
    assert "sk-ant-1234567890abcdef" not in result
    assert "***MASKED***" in result


def test_mask_password():
    """测试 password 脱敏."""
    text = 'password: mySecretPass123'
    result = mask_sensitive(text)
    assert "mySecretPass123" not in result
    assert "***MASKED***" in result


def test_mask_api_key():
    """测试 API Key 脱敏."""
    text = "api_key=AIzaSyC1234567890abcdefghijklmnopq"
    result = mask_sensitive(text)
    assert "AIzaSyC1234567890abcdefghijklmnopq" not in result
    assert "***MASKED***" in result


def test_mask_ssh_private_key():
    """测试 SSH 私钥脱敏."""
    text = """
    -----BEGIN RSA PRIVATE KEY-----
    MIIEpAIBAAKCAQEA1234567890
    -----END RSA PRIVATE KEY-----
    """
    result = mask_sensitive(text)
    assert "BEGIN RSA PRIVATE KEY" not in result
    assert "***SSH_PRIVATE_KEY_MASKED***" in result


def test_mask_multiple_patterns():
    """测试多种模式混合."""
    text = """
    token: sk-test-123456
    password: secret123
    Authorization: Bearer abc123
    """
    result = mask_sensitive(text)
    assert "sk-test-123456" not in result
    assert "secret123" not in result
    assert "abc123" not in result
    assert result.count("***MASKED***") >= 2


def test_is_sensitive():
    """测试敏感信息检测."""
    assert is_sensitive("password: abc123") is True
    assert is_sensitive("token: sk-ant-1234567890abcdefghijk") is True  # 长度足够的 token
    assert is_sensitive("hello world") is False
    assert is_sensitive("") is False


def test_mask_dict_sensitive_keys():
    """测试字典脱敏（敏感键名）."""
    data = {
        "username": "admin",
        "password": "secret123",
        "api_key": "sk-test-456",
        "normal_field": "normal_value",
    }

    result = mask_dict(data)

    assert result["username"] == "admin"
    assert result["password"] == "***MASKED***"
    assert result["api_key"] == "***MASKED***"
    assert result["normal_field"] == "normal_value"


def test_mask_dict_nested():
    """测试嵌套字典脱敏."""
    data = {
        "config": {
            "database": {
                "password": "db_secret",
                "host": "localhost",
            }
        },
        "api": {
            "token": "bearer_token_123",
        },
    }

    result = mask_dict(data)

    assert result["config"]["database"]["password"] == "***MASKED***"
    assert result["config"]["database"]["host"] == "localhost"
    assert result["api"]["token"] == "***MASKED***"


def test_mask_dict_with_list():
    """测试包含列表的字典脱敏."""
    data = {
        "users": [
            {"name": "user1", "password": "pass1"},
            {"name": "user2", "password": "pass2"},
        ]
    }

    result = mask_dict(data)

    assert result["users"][0]["name"] == "user1"
    assert result["users"][0]["password"] == "***MASKED***"
    assert result["users"][1]["password"] == "***MASKED***"


def test_mask_dict_content_check():
    """测试字典值内容检查."""
    data = {
        "log": "Error: token=sk-test-123 failed",
        "message": "Normal log message",
    }

    result = mask_dict(data)

    assert "sk-test-123" not in result["log"]
    assert "***MASKED***" in result["log"]
    assert result["message"] == "Normal log message"


def test_empty_string():
    """测试空字符串."""
    assert mask_sensitive("") == ""
    assert mask_sensitive(None) == None
    assert is_sensitive("") is False
