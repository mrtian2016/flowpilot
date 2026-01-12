"""Integration tests for OpenAI Compatible API."""

import pytest
from fastapi.testclient import TestClient

from flowpilot.mcp.server import app


@pytest.fixture(name="client")
def client_fixture():
    """Create TestClient for FastAPI app."""
    with TestClient(app) as client:
        yield client


class TestOpenAICompatAPI:
    """OpenAI 兼容 API 测试."""

    def test_models_list(self, client: TestClient):
        """Test /v1/models endpoint."""
        response = client.get("/v1/models")
        assert response.status_code == 200

        data = response.json()
        assert data["object"] == "list"
        assert "data" in data
        assert isinstance(data["data"], list)

        # 检查模型格式
        if data["data"]:
            model = data["data"][0]
            assert "id" in model
            assert model["object"] == "model"
            assert model["owned_by"] == "flowpilot"

    def test_chat_completions_basic(self, client: TestClient, monkeypatch):
        """Test /v1/chat/completions basic request (mocked)."""
        # Mock the LLM provider to avoid actual API calls
        from unittest.mock import AsyncMock, MagicMock

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(
            return_value={
                "content": "Hello! How can I help you?",
                "tool_calls": [],
                "model": "gemini",
                "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                "stop_reason": "stop",
            }
        )

        # Patch the provider router
        def mock_get_provider(provider_name=None, scenario=None):
            return mock_provider

        from flowpilot.mcp import openai_compat

        original_func = openai_compat._get_provider_router

        def mock_router():
            router = MagicMock()
            router.get_provider = mock_get_provider
            router.list_providers = MagicMock(return_value=["claude", "gemini", "zhipu"])
            return router

        monkeypatch.setattr(openai_compat, "_get_provider_router", mock_router)

        # Make request
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemini",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify OpenAI format
        assert "id" in data
        assert data["object"] == "chat.completion"
        assert "created" in data
        assert data["model"] == "gemini"
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["message"]["content"] == "Hello! How can I help you?"
        assert data["choices"][0]["finish_reason"] == "stop"
        assert "usage" in data

    def test_chat_completions_invalid_model(self, client: TestClient):
        """Test /v1/chat/completions with invalid model."""
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "nonexistent-model",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        # Should return 400 for unknown provider
        assert response.status_code == 400

    def test_chat_completions_missing_messages(self, client: TestClient):
        """Test /v1/chat/completions without messages."""
        response = client.post(
            "/v1/chat/completions",
            json={"model": "gemini"},
        )

        # Should return 422 for validation error
        assert response.status_code == 422

    def test_models_list_with_auth(self, client: TestClient, monkeypatch):
        """Test /v1/models with API key authentication."""
        # Set API key
        monkeypatch.setenv("FLOWPILOT_API_KEY", "test-secret-key")

        # Without key - should fail
        # (Note: In current impl, missing key is allowed in dev mode)
        # We test with correct key
        response = client.get(
            "/v1/models", headers={"Authorization": "Bearer test-secret-key"}
        )
        assert response.status_code == 200

        # With wrong key - should fail
        response = client.get(
            "/v1/models", headers={"Authorization": "Bearer wrong-key"}
        )
        assert response.status_code == 401

    def test_chat_completions_stream_format(self, client: TestClient, monkeypatch):
        """Test /v1/chat/completions stream response format."""
        from unittest.mock import AsyncMock, MagicMock

        # Mock streaming provider
        async def mock_stream_chat(*args, **kwargs):
            yield {"content": "Hello"}
            yield {"content": " world"}
            yield {"content": "!"}

        mock_provider = MagicMock()
        mock_provider.stream_chat = mock_stream_chat

        def mock_get_provider(provider_name=None, scenario=None):
            return mock_provider

        from flowpilot.mcp import openai_compat

        def mock_router():
            router = MagicMock()
            router.get_provider = mock_get_provider
            router.list_providers = MagicMock(return_value=["gemini"])
            return router

        monkeypatch.setattr(openai_compat, "_get_provider_router", mock_router)

        # Make streaming request
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemini",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # Parse SSE content
        content = response.text
        assert "data:" in content
        assert "[DONE]" in content
