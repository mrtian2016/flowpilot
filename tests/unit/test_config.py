"""配置加载器测试."""

import os
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from flowpilot.config.loader import ConfigLoader, load_config
from flowpilot.config.schema import FlowPilotConfig
from flowpilot.core.db import Base
from flowpilot.core.models import LLMConfig, LLMProvider, Host, Tag


@pytest.fixture
def mock_db_session():
    """Create an in-memory SQLite database and session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Mock SessionLocal in loader.py to return this session
    # We need to mock the context manager: with SessionLocal() as db:
    class MockSessionContext:
        def __enter__(self):
            return session
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass # Don't close session here to allow inspection in tests
            
    with patch("flowpilot.config.loader.SessionLocal", return_value=MockSessionContext()), \
         patch("flowpilot.config.loader.DB_FILE") as mock_file:
         
        mock_file.exists.return_value = True # Pretend DB file exists
        yield session
    
    session.close()


@pytest.fixture
def sample_data(mock_db_session):
    """Insert sample data into DB."""
    session = mock_db_session
    
    # LLM Config
    llm_config = LLMConfig(default_provider="claude")
    session.add(llm_config)
    session.flush()
    
    provider = LLMProvider(
        llm_config_id=llm_config.id,
        name="claude",
        model="claude-sonnet-4.5",
        api_key_env="ANTHROPIC_API_KEY",
        max_tokens=4096,
        temperature=0.7
    )
    session.add(provider)
    
    # Host
    host = Host(
        name="test-host",
        env="dev",
        user="ubuntu",
        addr="192.168.1.100",
        port=22
    )
    session.add(host)
    
    session.commit()


def test_load_valid_config(mock_db_session, sample_data):
    """测试加载配置."""
    loader = ConfigLoader()
    config = loader.load()

    assert isinstance(config, FlowPilotConfig)
    assert config.llm.default_provider == "claude"
    assert "claude" in config.llm.providers
    assert "test-host" in config.hosts
    assert config.hosts["test-host"].addr == "192.168.1.100"


def test_load_empty_db(mock_db_session):
    """Test loading from empty DB."""
    loader = ConfigLoader()
    config = loader.load()
    
    assert isinstance(config, FlowPilotConfig)
    assert config.llm.default_provider == "claude" # Default in code if not found


def test_validate_success(mock_db_session):
    """测试配置校验成功."""
    loader = ConfigLoader()
    is_valid, message = loader.validate()

    assert is_valid is True
    assert "配置加载正常" in message


def test_validate_failure():
    """测试配置校验失败."""
    # Mock exception during load
    with patch.object(ConfigLoader, "load", side_effect=Exception("DB Error")):
        loader = ConfigLoader()
        is_valid, message = loader.validate()

        assert is_valid is False
        assert "配置加载失败" in message


def test_get_api_key():
    """测试获取 API Key."""
    with patch.dict(os.environ, {"TEST_API_KEY": "sk-test-12345"}):
        api_key = ConfigLoader.get_api_key("TEST_API_KEY")
        assert api_key == "sk-test-12345"

    # 测试不存在的环境变量
    api_key = ConfigLoader.get_api_key("NONEXISTENT_KEY")
    assert api_key is None


def test_load_config_shortcut(mock_db_session, sample_data):
    """测试 load_config 快捷函数."""
    config = load_config()

    assert isinstance(config, FlowPilotConfig)
    assert config.llm.default_provider == "claude"


def test_hybrid_loading(mock_db_session, tmp_path):
    """测试混合加载 (YAML + DB)."""
    # 1. 创建临时 YAML 配置文件
    yaml_content = """
    llm:
      default_provider: yaml_provider
      providers:
        yaml_provider:
          model: yaml-model
          api_key_env: YAML_KEY
    hosts:
      yaml-host:
        env: yaml
        addr: yaml.host
        user: yaml-user
      shared-host:
        env: yaml
        addr: shared.yaml
        user: yaml-user
    policies:
      - name: yaml-policy
        condition:
          type: keywords
          keywords: ["yaml"]
        effect: allow
        message: yaml rule
    """
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content, encoding="utf-8")

    # 2. 准备数据库数据 (Override)
    session = mock_db_session
    
    # DB Host Config (override shared-host)
    host1 = Host(name="db-host", env="db", addr="db.host", user="db-user")
    host2 = Host(name="shared-host", env="db", addr="shared.db", user="db-user") # Override
    session.add_all([host1, host2])
    
    # DB Policy (append)
    from flowpilot.core.models import PolicyRule
    policy = PolicyRule(
        name="db-policy",
        condition={"type": "keywords", "keywords": ["db"]},
        effect="deny",
        message="db rule"
    )
    session.add(policy)
    session.commit()

    # 3. 加载配置
    loader = ConfigLoader(config_path=config_file)
    config = loader.load()

    # 验证 Hosts
    assert "yaml-host" in config.hosts          # From YAML
    assert config.hosts["yaml-host"].env == "yaml"
    
    assert "db-host" in config.hosts            # From DB
    assert config.hosts["db-host"].env == "db"
    
    assert "shared-host" in config.hosts        # Merged
    assert config.hosts["shared-host"].addr == "shared.db"  # DB Overrides YAML
    assert config.hosts["shared-host"].user == "db-user"

    # 验证 Policies (Append)
    policy_names = {p.name for p in config.policies}
    assert "yaml-policy" in policy_names
    assert "db-policy" in policy_names
    
    assert config.llm.default_provider == "yaml_provider" # Should come from YAML
    assert "yaml_provider" in config.llm.providers
