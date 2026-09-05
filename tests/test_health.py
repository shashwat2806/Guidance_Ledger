"""Smoke test for the Week 1 skeleton \u2014 confirms the app boots and the DB is reachable.

Run with: pytest
Requires Postgres running (docker compose up postgres) and DATABASE_URL set,
or falls back to the default in db/session.py.
"""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "guidanceledger"


def test_health_check_reaches_database():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "reachable"
