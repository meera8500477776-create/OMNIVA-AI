import os
from collections.abc import Generator

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_MODE", "demo")
os.environ.setdefault("SECRET_KEY", "test-only-key-not-for-production-0123456789")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import get_session
from app.core.rate_limit import reset_rate_limits
from app.db import models  # noqa: F401
from app.main import app


@pytest.fixture
def client() -> Generator[TestClient]:
    reset_rate_limits()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)
    engine.dispose()
