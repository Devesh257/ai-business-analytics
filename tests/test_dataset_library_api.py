from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import (
    TestClient,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from app.api import datasets
from app.db.base import Base
from app.models.dataset import (
    Dataset,
    DatasetVersion,
)
from app.models.user import User


@pytest.fixture
def library_context():
    engine = create_engine(
        "sqlite://",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(
        engine
    )

    SessionLocal = sessionmaker(
        bind=engine,
    )

    with SessionLocal() as db:
        user_a = User(
            email="a@example.com",
            hashed_password="unused",
        )

        user_b = User(
            email="b@example.com",
            hashed_password="unused",
        )

        db.add_all([
            user_a,
            user_b,
        ])

        db.flush()

        dataset_a = Dataset(
            name="A Revenue",
            user_id=user_a.id,
        )

        dataset_b = Dataset(
            name="B Private",
            user_id=user_b.id,
        )

        db.add_all([
            dataset_a,
            dataset_b,
        ])

        db.flush()

        db.add_all([
            DatasetVersion(
                dataset_id=dataset_a.id,
                version_number=1,
                file_name="a-v1.csv",
                file_path="/tmp/a-v1.csv",
            ),
            DatasetVersion(
                dataset_id=dataset_a.id,
                version_number=2,
                file_name="a-v2.csv",
                file_path="/tmp/a-v2.csv",
            ),
            DatasetVersion(
                dataset_id=dataset_b.id,
                version_number=1,
                file_name="b-v1.csv",
                file_path="/tmp/b-v1.csv",
            ),
        ])

        db.commit()

        ids = {
            "user_a": user_a.id,
            "user_b": user_b.id,
            "dataset_a": dataset_a.id,
            "dataset_b": dataset_b.id,
        }

    current_user = {
        "id": ids["user_a"],
    }

    app = FastAPI()
    app.include_router(
        datasets.router
    )

    def override_db():
        db = SessionLocal()

        try:
            yield db
        finally:
            db.close()

    def override_user():
        return SimpleNamespace(
            id=current_user["id"],
            is_active=True,
        )

    app.dependency_overrides[
        datasets.get_db
    ] = override_db

    app.dependency_overrides[
        datasets.get_current_user
    ] = override_user

    with TestClient(app) as client:
        yield {
            "client": client,
            "ids": ids,
            "current_user": (
                current_user
            ),
        }


def test_dataset_library_is_owner_scoped(
    library_context,
):
    response = library_context[
        "client"
    ].get(
        "/datasets"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["count"] == 1

    dataset = body["datasets"][0]

    assert dataset["name"] == (
        "A Revenue"
    )

    assert dataset[
        "version_count"
    ] == 2

    assert (
        dataset[
            "latest_version"
        ]["version_number"]
        == 2
    )

    assert (
        dataset[
            "latest_version"
        ]["file_name"]
        == "a-v2.csv"
    )


def test_user_only_sees_own_library(
    library_context,
):
    library_context[
        "current_user"
    ]["id"] = library_context[
        "ids"
    ]["user_b"]

    response = library_context[
        "client"
    ].get(
        "/datasets"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["count"] == 1

    assert (
        body["datasets"][0]["name"]
        == "B Private"
    )


def test_owner_can_list_versions(
    library_context,
):
    dataset_id = library_context[
        "ids"
    ]["dataset_a"]

    response = library_context[
        "client"
    ].get(
        f"/datasets/{dataset_id}/versions"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["count"] == 2

    assert [
        item["version_number"]
        for item in body[
            "versions"
        ]
    ] == [
        2,
        1,
    ]


def test_other_user_cannot_list_versions(
    library_context,
):
    library_context[
        "current_user"
    ]["id"] = library_context[
        "ids"
    ]["user_b"]

    dataset_id = library_context[
        "ids"
    ]["dataset_a"]

    response = library_context[
        "client"
    ].get(
        f"/datasets/{dataset_id}/versions"
    )

    assert response.status_code == 404


def test_library_requires_authentication():
    app = FastAPI()
    app.include_router(
        datasets.router
    )

    with TestClient(app) as client:
        response = client.get(
            "/datasets"
        )

    assert response.status_code == 401
