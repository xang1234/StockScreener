"""
Tests for /livez, /readyz, and /health endpoints.
"""
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock
import httpx

from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestLivez:
    async def test_returns_200(self, client):
        response = await client.get("/livez")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
class TestReadyz:
    async def test_healthy_when_db_and_redis_up(self, client):
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        # Mock engine.connect() to return a table count > 0
        mock_result = MagicMock()
        mock_result.scalar.return_value = 15  # 15 tables in schema
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        with patch("app.main.get_redis_client", return_value=mock_redis), \
             patch("app.main.engine", mock_engine):
            response = await client.get("/readyz")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["checks"]["database"] == "ok"
            assert data["checks"]["redis"] == "ok"

    async def test_degraded_when_redis_unavailable(self, client):
        """Redis is a soft dependency — unavailable Redis degrades but doesn't fail."""
        with patch("app.main.get_redis_client", return_value=None):
            response = await client.get("/readyz")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert "warning" in data["checks"]["redis"]

    async def test_degraded_when_redis_ping_fails(self, client):
        """Redis connection error results in degraded (200), not unhealthy (503)."""
        mock_client = MagicMock()
        mock_client.ping.side_effect = ConnectionError("refused")
        with patch("app.main.get_redis_client", return_value=mock_client):
            response = await client.get("/readyz")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert "ConnectionError" in data["checks"]["redis"]

    async def test_503_when_db_unavailable(self, client):
        with patch("app.main.engine") as mock_engine:
            mock_engine.connect.side_effect = Exception("db down")
            response = await client.get("/readyz")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data["checks"]["database"]

    async def test_503_when_db_has_no_tables(self, client):
        """Empty schema (count=0 from sqlite_master) is treated as unhealthy."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0  # No tables
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        with patch("app.main.engine", mock_engine):
            response = await client.get("/readyz")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "no tables" in data["checks"]["database"]


@pytest.mark.asyncio
class TestHealthDeprecated:
    async def test_returns_deprecated_flag(self, client):
        response = await client.get("/health")
        data = response.json()
        assert data["deprecated"] is True
        assert data["use_instead"] == "/readyz"

    async def test_mirrors_readyz_status(self, client):
        readyz_response = await client.get("/readyz")
        health_response = await client.get("/health")
        assert readyz_response.status_code == health_response.status_code
        # Health has extra fields
        health_data = health_response.json()
        assert "checks" in health_data
        assert "status" in health_data
