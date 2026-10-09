import io
from pathlib import Path

import pytest

from resume_scanner.api import create_app

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data" / "resumes"


@pytest.fixture()
def client():
    app = create_app(":memory:")
    app.testing = True
    return app.test_client()


def make_job(client):
    r = client.post("/api/jobs", json={"title": "ML Engineer",
                                       "description": "Requirements: Python, PyTorch, SQL, NLP. 1+ years experience."})
    assert r.status_code == 201
    return r.get_json()


def test_health(client):
    assert client.get("/api/health").get_json()["status"] == "ok"


def test_job_validation(client):
    assert client.post("/api/jobs", json={"title": "x"}).status_code == 400


def test_upload_screen_and_export(client):
    job = make_job(client)
    files = [(open(SAMPLES / n, "rb"), n) for n in ("aarav_mehta.pdf", "fatima_sheikh.pdf", "priya_raman.docx")]
    files.append((io.BytesIO(b"not an image"), "photo.png"))
    r = client.post(f"/api/jobs/{job['id']}/resumes", data={"files": files}, content_type="multipart/form-data")
    assert r.status_code == 201
    body = r.get_json()
    assert len(body["screened"]) == 3
    assert body["failed"][0]["filename"] == "photo.png"

    cands = client.get(f"/api/jobs/{job['id']}/candidates").get_json()
    assert cands[0]["score"] >= cands[-1]["score"]
    assert cands[0]["name"] in {"Aarav Mehta", "Priya Raman"}
    assert cands[-1]["name"] == "Fatima Sheikh" and cands[-1]["priority"] == "Low"

    r = client.patch(f"/api/candidates/{cands[0]['id']}", json={"status": "shortlisted"})
    assert r.get_json()["status"] == "shortlisted"
    assert client.patch(f"/api/candidates/{cands[0]['id']}", json={"status": "maybe"}).status_code == 400

    csv_text = client.get(f"/api/jobs/{job['id']}/export.csv").get_data(as_text=True)
    assert csv_text.splitlines()[0].startswith("rank,name,email")
    assert len(csv_text.strip().splitlines()) == 4


def test_demo_endpoint(client):
    job = client.post("/api/demo").get_json()
    assert sum(job["counts"].values()) == 12
    assert job["counts"]["High"] >= 1


def test_404s(client):
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/candidates/nope").status_code == 404
