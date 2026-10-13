import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from app.db.database import engine
from app.models.dataset import Dataset, DatasetVersion
from app.models.user import User


pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_MIGRATION_TEST") != "1",
    reason="requires the isolated PostgreSQL database configured by CI",
)


def test_postgres_migration_enforces_dataset_version_uniqueness():
    assert engine.dialect.name == "postgresql"

    user_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    connection = engine.connect()
    transaction = connection.begin()

    try:
        connection.execute(
            insert(User.__table__).values(
                id=user_id,
                email=(
                    "ci-migration@example.com"
                ),
                hashed_password=(
                    "test-password-hash"
                ),
                is_active=True,
                created_at=(
                    datetime.now(
                        timezone.utc
                    )
                ),
            )
        )

        connection.execute(
            insert(Dataset.__table__).values(
                id=dataset_id,
                user_id=user_id,
                name=(
                    "CI migration "
                    "constraint test"
                ),
                created_at=(
                    datetime.now(
                        timezone.utc
                    )
                ),
            )
        )
        version_values = {
            "dataset_id": dataset_id,
            "version_number": 1,
            "file_name": "ci.csv",
            "file_path": "/tmp/ci.csv",
            "created_at": datetime.now(timezone.utc),
        }
        connection.execute(
            insert(DatasetVersion.__table__).values(id=uuid.uuid4(), **version_values)
        )

        with pytest.raises(IntegrityError):
            connection.execute(
                insert(DatasetVersion.__table__).values(
                    id=uuid.uuid4(),
                    **version_values,
                )
            )
    finally:
        transaction.rollback()
        connection.close()
