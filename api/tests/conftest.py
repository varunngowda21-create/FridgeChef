import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.main import app


@pytest.fixture(scope="session")
def db_session():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from app.core.ratelimit import (
        general_rate_limiter,
        login_rate_limiter,
        recommendation_rate_limiter,
        scan_rate_limiter,
    )
    general_rate_limiter.clear()
    login_rate_limiter.clear()
    scan_rate_limiter.clear()
    recommendation_rate_limiter.clear()
    yield
    general_rate_limiter.clear()
    login_rate_limiter.clear()
    scan_rate_limiter.clear()
    recommendation_rate_limiter.clear()

