import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.services.dossier_service import DossierStore


@pytest.fixture(autouse=True)
def isolated_dossier_store(tmp_path, monkeypatch):
    """Use a fresh temp-file dossier store for each test."""
    from app.core.config import settings
    from app.services import dossier_service
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_file}")
    store = DossierStore()
    monkeypatch.setattr(dossier_service, "dossier_store", store)
    return store


def get_client():
    """Import app here to avoid import-time side effects in module scope."""
    from app.main import app
    return TestClient(app)


def test_health_endpoint():
    client = get_client()
    mock_pipeline = MagicMock()
    mock_pipeline.is_ready = True
    mock_pipeline.doc_count = 0
    with patch("app.services.retrieval_service.get_pipeline", return_value=mock_pipeline):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_create_and_list_dossier():
    client = get_client()
    response = client.post("/dossiers", json={"name": "Test Dossier", "description": "", "tags": []})
    assert response.status_code == 200
    dossier_id = response.json()["id"]

    response = client.get("/dossiers")
    assert response.status_code == 200
    ids = [d["id"] for d in response.json()["dossiers"]]
    assert dossier_id in ids


def test_get_dossier_not_found():
    client = get_client()
    response = client.get("/dossiers/nonexistent-id-xyz")
    assert response.status_code == 404


def test_delete_dossier():
    client = get_client()
    response = client.post("/dossiers", json={"name": "ToDelete", "description": "", "tags": []})
    assert response.status_code == 200
    dossier_id = response.json()["id"]

    response = client.delete(f"/dossiers/{dossier_id}")
    assert response.status_code == 200

    response = client.get(f"/dossiers/{dossier_id}")
    assert response.status_code == 404


def test_propagate_invalid_direction():
    client = get_client()
    response = client.post("/graph/propagate", json={
        "seed_scores": {"TNF": 1.0},
        "direction": "sideways"
    })
    assert response.status_code == 422


def test_propagate_valid_direction():
    client = get_client()
    response = client.post("/graph/propagate", json={
        "seed_scores": {"TNF": 1.0},
        "direction": "downstream"
    })
    assert response.status_code == 200


def test_image_hash_invalid_chars():
    client = get_client()
    response = client.get("/images/not!!valid")
    assert response.status_code == 400


def test_query_missing_question():
    client = get_client()
    response = client.post("/query", json={})
    assert response.status_code == 422


def test_compare_missing_disease_b():
    client = get_client()
    response = client.post("/compare", json={"disease_a": "RA"})
    assert response.status_code == 422


def test_metrics_endpoint():
    client = get_client()
    mock_pipeline = MagicMock()
    mock_pipeline.doc_count = 0
    mock_pipeline.is_ready = True
    with patch("app.services.retrieval_service.get_pipeline", return_value=mock_pipeline):
        response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "daily_cost_usd" in data
    assert "budget_ok" in data


# ------------------------------------------------------------------
# Unified SSE streaming endpoint — /query/stream
# ------------------------------------------------------------------

def test_query_stream_requires_question():
    """/query/stream without ?question= must return 422."""
    client = get_client()
    response = client.get("/query/stream")
    assert response.status_code == 422


def test_query_stream_mode_param_is_accepted():
    """mode=standard and mode=research are valid; 422 only when question is missing."""
    client = get_client()
    for mode in ("standard", "research"):
        response = client.get(f"/query/stream?mode={mode}")
        # question is required — 422 is the expected validation error,
        # NOT a 404 or 400 from an unknown mode parameter.
        assert response.status_code == 422, f"mode={mode} gave unexpected status"


def test_query_stream_standard_emits_sse():
    """GET /query/stream?mode=standard streams SSE events from the pipeline."""
    client = get_client()

    def _fake_stream(question, **kwargs):
        yield {"type": "citations", "data": []}
        yield {"type": "token", "text": "IL-6 signals via JAK-STAT."}
        yield {"type": "done", "model": "haiku", "cost": 0.001, "sources": []}

    mock_pipeline = MagicMock()
    mock_pipeline.stream = _fake_stream

    with patch("app.api.routes.pipeline", mock_pipeline):
        response = client.get(
            "/query/stream?question=What+is+IL-6%3F&mode=standard",
            headers={"Accept": "text/event-stream"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    body = response.text
    assert "citations" in body
    assert "token" in body
    assert "done" in body


def test_context_budget_caps_large_context():
    """_build_context stays within its character budget when fed large inputs."""
    from app.services.llm_service import LLMService
    from app.services.query_engine import SearchResult

    # Build a SearchResult with many large disease blocks
    import types
    sr = SearchResult()
    long_text = "x" * 5000
    sr.disease_hits = [
        {"disease_name": f"Disease {i}", "description": long_text,
         "pathogenic_mechanisms": [], "key_cell_types": [], "associated_genes": [],
         "references": []}
        for i in range(20)
    ]

    context, _ = LLMService._build_context([], sr, [], None)
    assert len(context) <= LLMService._CONTEXT_BUDGET, (
        f"Context exceeded budget: {len(context)} > {LLMService._CONTEXT_BUDGET}"
    )
