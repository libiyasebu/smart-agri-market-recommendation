import pytest
from unittest.mock import MagicMock
from sqlalchemy.engine import Engine
from app.config import Settings
from app.database import check_db_connection
from scripts.test_database import mask_db_url


def test_database_url_dialect_normalization():
    # When user provides postgresql://
    s1 = Settings(DATABASE_URL="postgresql://postgres:secret123@localhost:5432/agri_mini_db")
    assert s1.sync_database_url == "postgresql+psycopg2://postgres:secret123@localhost:5432/agri_mini_db"

    # When user already provides postgresql+psycopg2://
    s2 = Settings(DATABASE_URL="postgresql+psycopg2://postgres:secret123@localhost:5432/agri_mini_db")
    assert s2.sync_database_url == "postgresql+psycopg2://postgres:secret123@localhost:5432/agri_mini_db"


def test_password_masking():
    url = "postgresql+psycopg2://postgres:MySecretPassword123@localhost:5432/agri_mini_db"
    masked = mask_db_url(url)
    assert "MySecretPassword123" not in masked
    assert "***" in masked
    assert "postgres" in masked
    assert "agri_mini_db" in masked


def test_check_db_connection_success():
    mock_engine = MagicMock(spec=Engine)
    mock_conn = MagicMock()
    mock_result = (1, "agri_mini_db", "postgres", "PostgreSQL 17.11 on x86_64-pc-windows-msvc")
    mock_conn.execute.return_value.fetchone.return_value = mock_result
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    res = check_db_connection(custom_engine=mock_engine)

    assert res["status"] == "connected"
    assert res["alive"] is True
    assert res["database_name"] == "agri_mini_db"
    assert res["current_user"] == "postgres"
    assert "PostgreSQL 17.11" in res["server_version"]


def test_check_db_connection_failure():
    mock_engine = MagicMock(spec=Engine)
    mock_conn = MagicMock()
    # Query returns unexpected result (e.g. 0)
    mock_conn.execute.return_value.fetchone.return_value = (0, "agri_mini_db", "postgres", "version")
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with pytest.raises(ConnectionError) as exc:
        check_db_connection(custom_engine=mock_engine)
    assert "did not return expected result" in str(exc.value)
