import sys
import os

# Add project root to path so agents/ imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# SC-001: rate limiter defaults to ON now; tests hammer /auth/login etc. so
# disable it for the test runner. Set BEFORE importing app/rate_limiting.
os.environ.setdefault("HELIX_DISABLE_RATE_LIMIT", "1")

# SC-011: /auth/first-admin now requires X-Setup-Token matching SETUP_TOKEN.
# Tests bootstrap an admin in dozens of files; set a known token here (before
# app import so settings picks it up) and the `client` fixture injects the
# matching header by default.
os.environ.setdefault("SETUP_TOKEN", "test-setup-token")
TEST_SETUP_TOKEN = os.environ["SETUP_TOKEN"]

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.db.session import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql://helix:helix_password@localhost:5432/helix_test"


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Mock Redis so token revocation doesn't need a real Redis in tests
    mock_redis = MagicMock()
    mock_redis.exists.return_value = False
    mock_redis.setex.return_value = True

    app.dependency_overrides[get_db] = override_get_db
    with patch("app.core.redis_client._client", mock_redis):
        with patch("app.core.redis_client.get_redis", return_value=mock_redis):
            with TestClient(app) as c:
                # SC-011: inject the setup token on every request by default
                # so the many tests that POST /auth/first-admin keep working.
                # Harmless on other endpoints (the header is just ignored).
                c.headers.update({"X-Setup-Token": TEST_SETUP_TOKEN})
                yield c
    app.dependency_overrides.clear()
