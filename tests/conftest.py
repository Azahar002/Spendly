import tempfile
import os
import pytest
import database.db as db_module
from app import app as flask_app


@pytest.fixture(scope="session")
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    db_module.DB_PATH = db_path
    flask_app.config["TESTING"] = True
    with flask_app.app_context():
        db_module.init_db()
        db_module.seed_db()
    yield flask_app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    return client
