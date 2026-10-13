import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetVersion
from app.models.user import User


def test_initial_migration_creates_and_enforces_dataset_version_uniqueness(tmp_path):
    database_path = tmp_path / "migrated.db"
    database_url = f"sqlite:///{database_path}"
    project_root = Path(__file__).resolve().parents[1]

    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert {"datasets", "dataset_versions", "analysis_runs"} <= set(
        inspector.get_table_names()
    )
    assert {
        "name": "uq_dataset_versions_dataset_id_version_number",
        "column_names": ["dataset_id", "version_number"],
    } in inspector.get_unique_constraints("dataset_versions")

    dataset_columns = {
        column["name"]: column
        for column in inspector.get_columns(
            "datasets"
        )
    }

    assert (
        dataset_columns[
            "user_id"
        ]["nullable"]
        is False
    )

    with Session(engine) as session:
        user = User(
            email="migration@example.com",
            hashed_password="test-password-hash",
        )

        session.add(user)
        session.flush()

        dataset = Dataset(
            name="Migration test",
            user_id=user.id,
        )

        session.add(dataset)
        session.flush()
        session.add(
            DatasetVersion(
                id=uuid.uuid4(),
                dataset_id=dataset.id,
                version_number=1,
                file_name="first.csv",
                file_path="/tmp/first.csv",
            )
        )
        session.commit()

        session.add(
            DatasetVersion(
                id=uuid.uuid4(),
                dataset_id=dataset.id,
                version_number=1,
                file_name="duplicate.csv",
                file_path="/tmp/duplicate.csv",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
