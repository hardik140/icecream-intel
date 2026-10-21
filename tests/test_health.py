from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import SAMPLE

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_upload_table_and_list():
    with (SAMPLE / "sales.csv").open("rb") as fh:
        r = client.post("/data", files={"file": ("sales.csv", fh)}, data={"table_name": "sales"})
    assert r.status_code == 201, r.text
    assert client.get("/data/tables").json()[0]["table"] == "sales"


def test_upload_markdown_document_gets_indexed():
    with (SAMPLE / "operations_sop.md").open("rb") as fh:
        r = client.post("/documents", files={"file": ("operations_sop.md", fh)})
    assert r.status_code == 202, r.text
    docs = client.get("/documents").json()  # TestClient runs background tasks before returning
    assert docs[0]["status"] == "ready"
    assert client.delete(f"/documents/{docs[0]['doc_id']}").status_code == 204
    assert client.get("/documents").json() == []


def test_errors_use_one_shape():
    r = client.post("/documents", files={"file": ("x.exe", b"nope")})
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "http_error"
    assert client.post("/chat", json={"question": ""}).json()["error"]["code"] == "validation_error"


def test_llm_quota_exhaustion_returns_429(monkeypatch):
    from langchain_google_genai.chat_models import GoogleRateLimitError

    def boom(question):
        raise GoogleRateLimitError("429 RESOURCE_EXHAUSTED")
    monkeypatch.setattr("app.api.chat.ask", boom)
    r = TestClient(app, raise_server_exceptions=False).post("/chat", json={"question": "Top flavours?"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "llm_quota_exceeded"
