"""Tests for GET /mastery, GET /mastery/summary, and GET /recommendations."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swetrack.api import app, get_db_session
from swetrack.domains.learning.services import create_activity
from swetrack.domains.skills.taxonomy import TAXONOMY
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db


@pytest.fixture
def session(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'test_mastery.db'}")
    init_db(engine)
    session = get_sessionmaker(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(session):
    def _override_get_db_session():
        yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db_session, None)


def test_mastery_endpoint_returns_every_taxonomy_skill_by_default(client):
    response = client.get("/mastery")

    assert response.status_code == 200
    assert len(response.json()) == len(TAXONOMY)


def test_mastery_endpoint_respects_top_k(client):
    response = client.get("/mastery", params={"top_k": 3})

    assert response.status_code == 200
    assert len(response.json()) == 3


def test_mastery_endpoint_filters_by_category(client):
    response = client.get("/mastery", params={"category": "algorithms"})

    assert response.status_code == 200
    body = response.json()
    assert body
    assert all(item["category"] == "algorithms" for item in body)


def test_mastery_endpoint_rejects_unknown_category(client):
    response = client.get("/mastery", params={"category": "not-a-real-category"})
    assert response.status_code == 422


def test_mastery_summary_endpoint_returns_coding_and_system_design_rollups(client):
    response = client.get("/mastery/summary")

    assert response.status_code == 200
    body = response.json()
    assert 0.0 <= body["coding"] <= 1.0
    assert 0.0 <= body["system_design"] <= 1.0
    assert len(body["by_category"]) == 8


def test_recommendations_endpoint_returns_a_list(client):
    response = client.get("/recommendations")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_recommendations_endpoint_respects_top_k(client, session):
    create_activity(
        session, slug="graph-practice", title="Graph Practice", activity_type="concept_review", skill_ids=["graphs"]
    )
    create_activity(
        session, slug="tree-practice", title="Tree Practice", activity_type="concept_review", skill_ids=["trees"]
    )

    response = client.get("/recommendations", params={"top_k": 1})

    assert response.status_code == 200
    assert len(response.json()) == 1
