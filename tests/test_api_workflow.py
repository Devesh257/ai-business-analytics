from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import analysis_runs, datasets
from app.models.analysis import AnalysisRun
from app.models.dataset import DatasetVersion


class FakeQuery:
    def __init__(self, first_item=None, all_items=None):
        self.first_item = first_item
        self.all_items = all_items or []

    def filter(self, *args, **kwargs):
        return self

    def with_for_update(self):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.first_item

    def all(self):
        return self.all_items


class FakeDB:
    def __init__(
        self,
        first_by_model=None,
        all_by_model=None,
    ):
        self.first_by_model = first_by_model or {}
        self.all_by_model = all_by_model or {}

        self.added = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False

    def query(self, model):
        return FakeQuery(
            first_item=self.first_by_model.get(model),
            all_items=self.all_by_model.get(model, []),
        )

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushed = True

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def make_client(
    fake_db,
    current_user_id=None,
):
    app = FastAPI()

    app.include_router(datasets.router)
    app.include_router(analysis_runs.router)

    user = SimpleNamespace(
        id=current_user_id or uuid4(),
        is_active=True,
    )

    def override_db():
        yield fake_db

    def override_current_user():
        return user

    app.dependency_overrides[
        datasets.get_db
    ] = override_db

    app.dependency_overrides[
        analysis_runs.get_db
    ] = override_db

    app.dependency_overrides[
        datasets.get_current_user
    ] = override_current_user

    app.dependency_overrides[
        analysis_runs.get_current_user
    ] = override_current_user

    return TestClient(app)


def make_dataset_version(
    file_path,
):
    return SimpleNamespace(
        id=uuid4(),
        dataset_id=uuid4(),
        version_number=1,
        file_name="business.csv",
        file_path=str(file_path),
    )


def test_api_upload_creates_dataset_and_first_version(
    tmp_path,
    monkeypatch,
):
    fake_db = FakeDB()

    client = make_client(
        fake_db
    )

    monkeypatch.setattr(
        datasets,
        "UPLOAD_DIR",
        tmp_path,
    )

    response = client.post(
        "/datasets/upload",
        files={
            "file": (
                "business.csv",
                (
                    b"Revenue,Cost\n"
                    b"100,80\n"
                    b"200,160\n"
                    b"300,240\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["message"]
        == "Dataset uploaded successfully"
    )

    assert body["version_number"] == 1
    assert body["file_name"] == "business.csv"

    UUID(body["dataset_id"])
    version_id = UUID(
        body["dataset_version_id"]
    )

    assert fake_db.flushed is True
    assert fake_db.committed is True

    # Dataset + DatasetVersion
    assert len(fake_db.added) == 2

    stored_files = list(
        tmp_path.glob("*.csv")
    )

    assert len(stored_files) == 1
    assert stored_files[0].stem == str(version_id)


def test_api_dataset_stage_endpoints_return_expected_contracts(
    tmp_path,
    monkeypatch,
):
    file_path = (
        tmp_path
        / "business.csv"
    )

    file_path.write_text(
        "Revenue,Cost,Department\n"
        "100,80,North\n"
        "200,160,South\n"
        "300,240,North\n"
    )

    version = make_dataset_version(
        file_path
    )

    fake_db = FakeDB(
        first_by_model={
            DatasetVersion: version,
        }
    )

    client = make_client(
        fake_db
    )

    validation = {
        "valid": True,
        "errors": [],
    }

    pii = {
        "pii_detected": False,
        "protected_columns": {},
        "safe_columns": [
            "Revenue",
            "Cost",
            "Department",
        ],
        "detection_methods": {
            "column_name": {},
            "cell_value": {},
        },
    }

    profile = {
        "rows": 3,
        "columns": 3,
    }

    semantics = {
        "columns": {
            "Revenue": {
                "role": "measure",
            },
            "Cost": {
                "role": "measure",
            },
            "Department": {
                "role": "dimension",
            },
        }
    }

    plan = {
        "measures": [
            "Revenue",
            "Cost",
        ],
        "dimensions": [
            "Department",
        ],
        "dates": [],
        "identifiers": [],
        "analyses": [],
    }

    monkeypatch.setattr(
        datasets,
        "validate_dataset",
        lambda path: validation,
    )

    monkeypatch.setattr(
        datasets,
        "analyze_pii",
        lambda path: pii,
    )

    monkeypatch.setattr(
        datasets,
        "profile_dataset",
        lambda path, protected: profile,
    )

    monkeypatch.setattr(
        datasets,
        "infer_semantics",
        lambda path, protected: semantics,
    )

    monkeypatch.setattr(
        datasets,
        "build_analytics_plan",
        lambda received_profile, received_semantics: plan,
    )

    version_id = str(
        version.id
    )

    response = client.post(
        f"/datasets/{version_id}/validate"
    )

    assert response.status_code == 200
    assert (
        response.json()["validation"]
        == validation
    )

    response = client.post(
        f"/datasets/{version_id}/pii-scan"
    )

    assert response.status_code == 200
    assert (
        response.json()["pii_scan"]
        == pii
    )

    response = client.get(
        f"/datasets/{version_id}/profile"
    )

    assert response.status_code == 200
    assert (
        response.json()["profile"]
        == profile
    )

    response = client.get(
        f"/datasets/{version_id}/semantics"
    )

    assert response.status_code == 200
    assert (
        response.json()["semantics"]
        == semantics
    )

    response = client.get(
        f"/datasets/{version_id}/plan"
    )

    assert response.status_code == 200

    assert (
        response.json()["analytics_plan"]
        == plan
    )


def test_api_profile_and_semantics_receive_protected_columns(
    tmp_path,
    monkeypatch,
):
    file_path = (
        tmp_path
        / "protected.csv"
    )

    file_path.write_text(
        "Email,Revenue\n"
        "person@example.com,100\n"
    )

    version = make_dataset_version(
        file_path
    )

    fake_db = FakeDB(
        first_by_model={
            DatasetVersion: version,
        }
    )

    client = make_client(
        fake_db
    )

    pii = {
        "pii_detected": True,
        "protected_columns": {
            "Email": "email",
        },
        "safe_columns": [
            "Revenue",
        ],
        "detection_methods": {
            "column_name": {
                "Email": "email",
            },
            "cell_value": {
                "Email": "email",
            },
        },
    }

    received_profile_protection = []
    received_semantic_protection = []

    monkeypatch.setattr(
        datasets,
        "analyze_pii",
        lambda path: pii,
    )

    def fake_profile(
        path,
        protected_columns,
    ):
        received_profile_protection.append(
            protected_columns
        )

        return {
            "rows": 1,
            "columns": 1,
        }

    def fake_semantics(
        path,
        protected_columns,
    ):
        received_semantic_protection.append(
            protected_columns
        )

        return {
            "columns": {
                "Revenue": {
                    "role": "measure",
                }
            }
        }

    monkeypatch.setattr(
        datasets,
        "profile_dataset",
        fake_profile,
    )

    monkeypatch.setattr(
        datasets,
        "infer_semantics",
        fake_semantics,
    )

    version_id = str(
        version.id
    )

    response = client.get(
        f"/datasets/{version_id}/profile"
    )

    assert response.status_code == 200

    response = client.get(
        f"/datasets/{version_id}/semantics"
    )

    assert response.status_code == 200

    assert received_profile_protection == [
        {
            "Email": "email",
        }
    ]

    assert received_semantic_protection == [
        {
            "Email": "email",
        }
    ]


def test_api_analyze_delegates_to_phase1_pipeline(
    tmp_path,
    monkeypatch,
):
    file_path = (
        tmp_path
        / "business.csv"
    )

    file_path.write_text(
        "Revenue,Cost\n"
        "100,80\n"
        "200,160\n"
    )

    version = make_dataset_version(
        file_path
    )

    fake_db = FakeDB(
        first_by_model={
            DatasetVersion: version,
        }
    )

    client = make_client(
        fake_db
    )

    captured = {}

    run_id = uuid4()

    def fake_run_phase1_analysis(
        file_path,
        dataset_id=None,
        dataset_version_id=None,
    ):
        captured["file_path"] = file_path
        captured["dataset_id"] = dataset_id
        captured[
            "dataset_version_id"
        ] = dataset_version_id

        return {
            "status": "completed",
            "analysis_run_id": str(
                run_id
            ),
            "analysis_results": [],
            "ranked_insights": [],
        }

    monkeypatch.setattr(
        datasets,
        "run_phase1_analysis",
        fake_run_phase1_analysis,
    )

    response = client.post(
        f"/datasets/{version.id}/analyze"
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["analysis_run_id"]
        == str(run_id)
    )

    assert (
        body["dataset_version_id"]
        == str(version.id)
    )

    assert (
        body["analysis"]["status"]
        == "completed"
    )

    assert (
        captured["file_path"]
        == str(file_path)
    )

    assert (
        captured["dataset_id"]
        == str(version.dataset_id)
    )

    assert (
        captured["dataset_version_id"]
        == str(version.id)
    )


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("post", "validate"),
        ("post", "pii-scan"),
        ("get", "profile"),
        ("get", "semantics"),
        ("get", "plan"),
        ("post", "analyze"),
    ],
)
def test_api_dataset_stage_endpoints_return_404_for_missing_version(
    method,
    suffix,
):
    fake_db = FakeDB(
        first_by_model={
            DatasetVersion: None,
        }
    )

    client = make_client(
        fake_db
    )

    missing_id = uuid4()

    response = getattr(
        client,
        method,
    )(
        f"/datasets/{missing_id}/{suffix}"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Dataset version not found."
    )


def test_api_get_analysis_run_returns_persisted_pipeline_state():
    analysis_run_id = uuid4()
    dataset_version_id = uuid4()

    created_at = datetime(
        2026,
        10,
        4,
        9,
        0,
        tzinfo=timezone.utc,
    )

    run = SimpleNamespace(
        id=analysis_run_id,
        dataset_version_id=dataset_version_id,
        status="completed",
        validation_result={
            "valid": True,
        },
        pii_result={
            "pii_detected": False,
        },
        profile_result={
            "rows": 100,
        },
        semantic_result={
            "columns": {},
        },
        plan_result={
            "analyses": [],
        },
        analysis_results=[
            {
                "type": "correlation",
            }
        ],
        discovered_insights=[],
        verified_insights=[],
        confidence_insights=[],
        scored_insights=[],
        ranked_insights=[],
        created_at=created_at,
        explained_insights=[],
        recommended_insights=[],
    )

    fake_db = FakeDB(
        first_by_model={
            AnalysisRun: run,
        }
    )

    client = make_client(
        fake_db
    )

    response = client.get(
        f"/analysis-runs/{analysis_run_id}"
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["id"]
        == str(analysis_run_id)
    )

    assert (
        body["dataset_version_id"]
        == str(dataset_version_id)
    )

    assert (
        body["status"]
        == "completed"
    )

    assert (
        body["validation_result"]
        == {
            "valid": True,
        }
    )

    assert body["analysis_results"] == [
        {
            "type": "correlation",
        }
    ]

    assert "explained_insights" in body
    assert "recommended_insights" in body


def test_api_analysis_run_returns_404_when_missing():
    fake_db = FakeDB(
        first_by_model={
            AnalysisRun: None,
        }
    )

    client = make_client(
        fake_db
    )

    response = client.get(
        f"/analysis-runs/{uuid4()}"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Analysis run not found"
    )


def test_api_lists_analysis_runs_for_dataset_version():
    dataset_version_id = uuid4()

    dataset_version = SimpleNamespace(
        id=dataset_version_id,
    )

    newest = SimpleNamespace(
        id=uuid4(),
        status="completed",
        created_at=datetime(
            2026,
            10,
            4,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    older = SimpleNamespace(
        id=uuid4(),
        status="partially_completed",
        created_at=datetime(
            2026,
            10,
            4,
            9,
            0,
            tzinfo=timezone.utc,
        ),
    )

    fake_db = FakeDB(
        first_by_model={
            DatasetVersion: dataset_version,
        },
        all_by_model={
            AnalysisRun: [
                newest,
                older,
            ],
        },
    )

    client = make_client(
        fake_db
    )

    response = client.get(
        (
            "/analysis-runs/"
            f"dataset-version/{dataset_version_id}"
        )
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["dataset_version_id"]
        == str(dataset_version_id)
    )

    assert body["count"] == 2

    assert len(
        body["analysis_runs"]
    ) == 2

    assert (
        body["analysis_runs"][0]["id"]
        == str(newest.id)
    )

    assert (
        body["analysis_runs"][0]["status"]
        == "completed"
    )

    assert (
        body["analysis_runs"][1]["id"]
        == str(older.id)
    )


def test_api_analysis_run_list_returns_404_for_missing_dataset_version():
    fake_db = FakeDB(
        first_by_model={
            DatasetVersion: None,
        },
        all_by_model={
            AnalysisRun: [],
        },
    )

    client = make_client(
        fake_db
    )

    response = client.get(
        (
            "/analysis-runs/"
            f"dataset-version/{uuid4()}"
        )
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Dataset version not found"
    )