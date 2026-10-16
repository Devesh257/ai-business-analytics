from pathlib import Path

import pytest

from app.services.dataset_storage import (
    DatasetStorageError,
    LocalDatasetStorage,
)


def test_local_storage_uses_portable_relative_reference(
    tmp_path,
):
    root = tmp_path / "storage"
    source = tmp_path / "source.csv"
    source.write_text(
        "amount\n10\n",
        encoding="utf-8",
    )

    storage = LocalDatasetStorage(root)

    reference = storage.store_file(
        source,
        "uploads/dataset.csv",
    )

    assert reference == "uploads/dataset.csv"
    assert not Path(reference).is_absolute()
    assert source.exists()

    with storage.materialize(reference) as materialized:
        assert materialized == (
            root
            / "uploads"
            / "dataset.csv"
        ).resolve()

        assert materialized.read_text(
            encoding="utf-8"
        ) == "amount\n10\n"


def test_local_storage_supports_legacy_absolute_reference(
    tmp_path,
):
    legacy_file = tmp_path / "legacy.csv"
    legacy_file.write_text(
        "amount\n20\n",
        encoding="utf-8",
    )

    storage = LocalDatasetStorage(
        tmp_path / "storage"
    )

    with storage.materialize(
        str(legacy_file)
    ) as materialized:
        assert materialized == legacy_file.resolve()


@pytest.mark.parametrize(
    "object_key",
    [
        "../secret.csv",
        "uploads/../secret.csv",
        "/tmp/secret.csv",
        r"uploads\secret.csv",
        "",
    ],
)
def test_local_storage_rejects_unsafe_object_keys(
    tmp_path,
    object_key,
):
    storage = LocalDatasetStorage(
        tmp_path / "storage"
    )

    source = tmp_path / "source.csv"
    source.write_text(
        "amount\n10\n",
        encoding="utf-8",
    )

    with pytest.raises(
        DatasetStorageError
    ):
        storage.store_file(
            source,
            object_key,
        )


def test_local_storage_missing_reference_fails_cleanly(
    tmp_path,
):
    storage = LocalDatasetStorage(
        tmp_path / "storage"
    )

    with pytest.raises(
        FileNotFoundError
    ):
        with storage.materialize(
            "uploads/missing.csv"
        ):
            pass


def test_local_storage_does_not_overwrite_existing_object(
    tmp_path,
):
    storage = LocalDatasetStorage(
        tmp_path / "storage"
    )

    first = tmp_path / "first.csv"
    first.write_text(
        "amount\n10\n",
        encoding="utf-8",
    )

    second = tmp_path / "second.csv"
    second.write_text(
        "amount\n20\n",
        encoding="utf-8",
    )

    storage.store_file(
        first,
        "uploads/dataset.csv",
    )

    with pytest.raises(
        FileExistsError
    ):
        storage.store_file(
            second,
            "uploads/dataset.csv",
        )


def test_local_storage_delete_removes_object(
    tmp_path,
):
    storage = LocalDatasetStorage(
        tmp_path / "storage"
    )

    source = tmp_path / "source.csv"
    source.write_text(
        "amount\n10\n",
        encoding="utf-8",
    )

    reference = storage.store_file(
        source,
        "uploads/dataset.csv",
    )

    stored_path = storage.resolve_reference(
        reference
    )

    assert stored_path.exists()

    storage.delete(reference)

    assert not stored_path.exists()


def test_reference_for_path_is_relative_inside_storage_root(
    tmp_path,
):
    root = tmp_path / "storage"
    upload = root / "uploads" / "dataset.csv"
    upload.parent.mkdir(
        parents=True
    )
    upload.write_text(
        "amount\n10\n",
        encoding="utf-8",
    )

    storage = LocalDatasetStorage(root)

    assert storage.reference_for_path(
        upload
    ) == "uploads/dataset.csv"


def test_reference_for_path_keeps_external_legacy_path_absolute(
    tmp_path,
):
    root = tmp_path / "storage"
    legacy = tmp_path / "legacy.csv"

    legacy.write_text(
        "amount\n10\n",
        encoding="utf-8",
    )

    storage = LocalDatasetStorage(root)

    reference = storage.reference_for_path(
        legacy
    )

    assert Path(reference).is_absolute()
    assert Path(reference) == legacy.resolve()
