from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_upload_rejects_non_pdf():
    response = client.post(
        "/api/upload",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are allowed."


def test_upload_rejects_invalid_pdf_signature():
    response = client.post(
        "/api/upload",
        files={"file": ("fake.pdf", b"not a pdf file", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "The uploaded file does not appear to be a valid PDF."
    )