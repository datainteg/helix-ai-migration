import sys
import os

# Add project root to path so agents/ imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

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
                yield c
    app.dependency_overrides.clear()
