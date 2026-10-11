import asyncio
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import HTTPException

from app.api import datasets


FAKE_CURRENT_USER = SimpleNamespace(id="test-user-id")


class FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *_args):
        return self

    def first(self):
        return self.result


class FakeDatabase:
    def __init__(self, result):
        self.result = result

    def query(self, _model):
        return FakeQuery(self.result)


class ChunkedUpload:
    def __init__(self, filename: str, chunks: list[bytes]):
        self.filename = filename
        self.chunks = iter(chunks)

    async def read(self, _size: int) -> bytes:
        return next(self.chunks, b"")


def test_profile_endpoint_excludes_detected_pii(tmp_path):
    file_path = tmp_path / "employees.csv"
    pd.DataFrame({"Email": ["a@example.com"], "Revenue": [125]}).to_csv(
        file_path, index=False
    )
    version = SimpleNamespace(file_path=str(file_path))

    response = datasets.profile_dataset_version("unused", FakeDatabase(version),
        current_user=FAKE_CURRENT_USER,
    )

    assert response["profile"]["column_names"] == ["Revenue"]
    assert "Email" not in response["profile"]["columns_profile"]


def test_semantics_endpoint_excludes_detected_pii(tmp_path):
    file_path = tmp_path / "employees.csv"
    pd.DataFrame({"Email": ["a@example.com"], "Revenue": [125]}).to_csv(
        file_path, index=False
    )
    version = SimpleNamespace(file_path=str(file_path))

    response = datasets.detect_dataset_semantics("unused", FakeDatabase(version),
        current_user=FAKE_CURRENT_USER,
    )

    assert "Email" not in response["semantics"]["columns"]
    assert response["semantics"]["columns"]["Revenue"]["role"] == "measure"


def test_plan_endpoint_excludes_detected_pii(tmp_path):
    file_path = tmp_path / "employees.csv"
    pd.DataFrame({"Email": ["a@example.com"], "Revenue": [125]}).to_csv(
        file_path, index=False
    )
    version = SimpleNamespace(file_path=str(file_path))

    response = datasets.create_analytics_plan("unused", FakeDatabase(version),
        current_user=FAKE_CURRENT_USER,
    )

    assert response["analytics_plan"]["measures"] == ["Revenue"]
    assert "Email" not in response["analytics_plan"]["measures"]


def test_upload_rejects_path_traversal_filename():
    with pytest.raises(HTTPException, match="Unsafe filename"):
        datasets._safe_upload_filename("../../report.csv")


def test_upload_rejects_mismatched_spreadsheet_content(tmp_path):
    file_path = tmp_path / "not-a-workbook.xlsx"
    file_path.write_bytes(b"not an xlsx file")

    with pytest.raises(ValueError, match="valid XLSX"):
        datasets._validate_uploaded_content(file_path, ".xlsx")


def test_upload_rejects_binary_csv_content(tmp_path):
    file_path = tmp_path / "binary.csv"
    file_path.write_bytes(b"\x00\x01\x02")

    with pytest.raises(ValueError, match="does not match"):
        datasets._validate_uploaded_content(file_path, ".csv")


def test_upload_enforces_size_limit_while_streaming(tmp_path, monkeypatch):
    monkeypatch.setattr(datasets, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(datasets, "MAX_UPLOAD_SIZE_BYTES", 10)
    upload = ChunkedUpload("report.csv", [b"Revenue\n123\n"])

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(datasets.upload_dataset(upload, None, object()))

    assert exc_info.value.status_code == 413
    assert list(tmp_path.iterdir()) == []
