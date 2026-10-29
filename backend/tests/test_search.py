from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_search_rejects_empty_query():
    response = client.post(
        "/api/search",
        json={"query": "", "top_k": 3},
    )

    assert response.status_code == 422


def test_search_rejects_top_k_above_limit():
    response = client.post(
        "/api/search",
        json={"query": "database", "top_k": 11},
    )

    assert response.status_code == 422