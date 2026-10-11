from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import analysis_runs, datasets
from app.db.base import Base
from app.models.analysis import AnalysisRun
from app.models.dataset import Dataset, DatasetVersion
from app.models.user import User


@pytest.fixture
def ownership_context(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    with TestingSessionLocal() as db:
        user_a = User(
            email="owner-a@example.com",
            hashed_password="unused-test-hash",
        )

        user_b = User(
            email="owner-b@example.com",
            hashed_password="unused-test-hash",
        )

        db.add_all([user_a, user_b])
        db.flush()

        dataset = Dataset(
            name="Owner A Dataset",
            user_id=user_a.id,
        )

        db.add(dataset)
        db.flush()

        version = DatasetVersion(
            dataset_id=dataset.id,
            version_number=1,
            file_name="private.csv",
            file_path=str(
                tmp_path / "private.csv"
            ),
        )

        db.add(version)
        db.flush()

        analysis_run = AnalysisRun(
            dataset_version_id=version.id,
            status="completed",
            validation_result={},
            pii_result={},
            profile_result={},
            semantic_result={},
            plan_result={},
            analysis_results=[],
            discovered_insights=[],
            verified_insights=[],
            confidence_insights=[],
            scored_insights=[],
            ranked_insights=[],
            explained_insights=[],
            recommended_insights=[],
        )

        db.add(analysis_run)
        db.commit()

        ids = {
            "user_a": user_a.id,
            "user_b": user_b.id,
            "dataset": dataset.id,
            "version": version.id,
            "analysis_run": analysis_run.id,
        }

    current_user = {
        "id": ids["user_b"],
    }

    app = FastAPI()
    app.include_router(datasets.router)
    app.include_router(analysis_runs.router)

    def override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_current_user():
        return SimpleNamespace(
            id=current_user["id"],
            is_active=True,
        )

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

    monkeypatch.setattr(
        datasets,
        "UPLOAD_DIR",
        tmp_path,
    )

    with TestClient(app) as client:
        yield {
            "client": client,
            "ids": ids,
            "current_user": current_user,
        }


def test_other_user_cannot_access_dataset_stages(
    ownership_context,
):
    client = ownership_context["client"]
    version_id = ownership_context[
        "ids"
    ]["version"]

    requests = [
        ("post", f"/datasets/{version_id}/validate"),
        ("post", f"/datasets/{version_id}/pii-scan"),
        ("get", f"/datasets/{version_id}/profile"),
        ("get", f"/datasets/{version_id}/semantics"),
        ("get", f"/datasets/{version_id}/plan"),
        ("post", f"/datasets/{version_id}/analyze"),
    ]

    for method, path in requests:
        response = getattr(client, method)(
            path
        )

        assert response.status_code == 404


def test_other_user_cannot_add_dataset_version(
    ownership_context,
):
    client = ownership_context["client"]
    dataset_id = ownership_context[
        "ids"
    ]["dataset"]

    response = client.post(
        "/datasets/upload",
        data={
            "dataset_id": str(dataset_id),
        },
        files={
            "file": (
                "new.csv",
                b"Revenue,Cost\n100,80\n",
                "text/csv",
            ),
        },
    )

    assert response.status_code == 404


def test_other_user_cannot_access_analysis_history(
    ownership_context,
):
    client = ownership_context["client"]
    version_id = ownership_context[
        "ids"
    ]["version"]

    response = client.get(
        "/analysis-runs/"
        f"dataset-version/{version_id}"
    )

    assert response.status_code == 404


def test_other_user_cannot_access_analysis_run(
    ownership_context,
):
    client = ownership_context["client"]
    analysis_run_id = ownership_context[
        "ids"
    ]["analysis_run"]

    response = client.get(
        f"/analysis-runs/{analysis_run_id}"
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "export_format",
    [
        "csv",
        "xlsx",
        "pdf",
    ],
)
def test_other_user_cannot_export_analysis_run(
    ownership_context,
    export_format,
):
    client = ownership_context["client"]
    analysis_run_id = ownership_context[
        "ids"
    ]["analysis_run"]

    response = client.get(
        f"/analysis-runs/{analysis_run_id}"
        f"/export/{export_format}"
    )

    assert response.status_code == 404


def test_owner_can_access_owned_analysis_resources(
    ownership_context,
):
    client = ownership_context["client"]
    ids = ownership_context["ids"]

    ownership_context[
        "current_user"
    ]["id"] = ids["user_a"]

    history = client.get(
        "/analysis-runs/"
        f"dataset-version/{ids['version']}"
    )

    assert history.status_code == 200

    analysis_run = client.get(
        f"/analysis-runs/{ids['analysis_run']}"
    )

    assert analysis_run.status_code == 200

    export = client.get(
        f"/analysis-runs/{ids['analysis_run']}"
        "/export/csv"
    )

    assert export.status_code == 200


def test_dataset_route_requires_authentication():
    app = FastAPI()
    app.include_router(datasets.router)

    class EmptyDB:
        def close(self):
            pass

    def override_db():
        yield EmptyDB()

    app.dependency_overrides[
        datasets.get_db
    ] = override_db

    with TestClient(app) as client:
        response = client.get(
            f"/datasets/{uuid4()}/profile"
        )

    assert response.status_code == 401
