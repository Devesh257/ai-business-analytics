from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.dataset import Dataset
from app.models.user import User
from app.security.passwords import hash_password


def make_session():
    engine = create_engine(
        "sqlite:///:memory:"
    )

    Base.metadata.create_all(engine)

    return sessionmaker(
        bind=engine
    )()


def test_dataset_can_belong_to_user():
    db = make_session()

    try:
        user = User(
            email="owner@example.com",
            hashed_password=hash_password(
                "Strong-Password-123!"
            ),
        )

        db.add(user)
        db.flush()

        dataset = Dataset(
            name="Revenue Data",
            user_id=user.id,
        )

        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        assert dataset.user_id == user.id
        assert dataset.user.email == (
            "owner@example.com"
        )
    finally:
        db.close()


def test_user_can_have_multiple_datasets():
    db = make_session()

    try:
        user = User(
            email="owner@example.com",
            hashed_password=hash_password(
                "Strong-Password-123!"
            ),
        )

        db.add(user)
        db.flush()

        db.add_all(
            [
                Dataset(
                    name="First Dataset",
                    user_id=user.id,
                ),
                Dataset(
                    name="Second Dataset",
                    user_id=user.id,
                ),
            ]
        )

        db.commit()
        db.refresh(user)

        names = {
            dataset.name
            for dataset in user.datasets
        }

        assert names == {
            "First Dataset",
            "Second Dataset",
        }
    finally:
        db.close()



def test_dataset_owner_is_required():
    assert (
        Dataset.__table__
        .c.user_id.nullable
        is False
    )
