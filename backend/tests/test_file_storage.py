
from pathlib import Path

import pytest

from app.services import file_storage


def test_save_pdf_creates_file(tmp_path, monkeypatch):
    # Use a temporary upload directory
    upload_dir = tmp_path / "storage" / "uploads"
    monkeypatch.setattr(file_storage, "UPLOAD_DIR", upload_dir)

    contents = b"%PDF-1.4 test pdf content"

    storage_path = file_storage.save_pdf(contents)

    saved_file = upload_dir / Path(storage_path).name

    assert saved_file.exists()
    assert saved_file.read_bytes() == contents
    assert storage_path.startswith("storage/uploads/")
    assert storage_path.endswith(".pdf")


def test_save_pdf_generates_unique_filenames(tmp_path, monkeypatch):
    upload_dir = tmp_path / "storage" / "uploads"
    monkeypatch.setattr(file_storage, "UPLOAD_DIR", upload_dir)

    first_path = file_storage.save_pdf(b"%PDF-1.4 first")
    second_path = file_storage.save_pdf(b"%PDF-1.4 second")

    assert first_path != second_path


def test_get_pdf_path_returns_valid_path(tmp_path, monkeypatch):
    upload_dir = tmp_path / "storage" / "uploads"
    monkeypatch.setattr(file_storage, "UPLOAD_DIR", upload_dir)

    contents = b"%PDF-1.4 test pdf content"
    storage_path = file_storage.save_pdf(contents)

    resolved_path = file_storage.get_pdf_path(storage_path)

    assert resolved_path.exists()
    assert resolved_path.is_file()
    assert resolved_path.read_bytes() == contents
    assert resolved_path.is_relative_to(upload_dir.resolve())


def test_get_pdf_path_rejects_path_traversal(tmp_path, monkeypatch):
    upload_dir = tmp_path / "storage" / "uploads"
    monkeypatch.setattr(file_storage, "UPLOAD_DIR", upload_dir)

    with pytest.raises(ValueError, match="Invalid storage path"):
        file_storage.get_pdf_path("../../.env")
