import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TOKEN = "test-token"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        demo_mode=True,
        demo_token=TOKEN,
        demo_latency_seconds=0.2,
        log_level="INFO",
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def auth():
    return {"X-Demo-Token": TOKEN}
