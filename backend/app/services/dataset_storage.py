from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import ContextManager, Iterator, Protocol


class DatasetStorageError(ValueError):
    """Raised when a dataset storage reference is unsafe or invalid."""


class DatasetStorage(Protocol):
    """
    Storage contract for persisted dataset files.

    A future object-storage backend can implement the same contract by
    uploading from a local staging file and materializing objects into
    temporary local files for deterministic analytics.
    """

    def store_file(
        self,
        source_path: str | Path,
        object_key: str,
    ) -> str:
        """Persist a local file and return its stable storage reference."""

    def materialize(
        self,
        reference: str,
    ) -> ContextManager[Path]:
        """Expose a stored dataset as a local filesystem path."""

    def delete(
        self,
        reference: str,
    ) -> None:
        """Delete a persisted dataset object if it exists."""


class LocalDatasetStorage:
    """
    Local-filesystem implementation of DatasetStorage.

    New files use relative storage references such as:

        uploads/<uuid>.csv

    Legacy absolute filesystem references remain readable so existing
    DatasetVersion rows do not need an immediate database migration.
    """

    def __init__(
        self,
        root_dir: str | Path,
    ) -> None:
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.root_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    @staticmethod
    def _normalize_object_key(
        object_key: str,
    ) -> str:
        if (
            not object_key
            or "\x00" in object_key
            or "\\" in object_key
        ):
            raise DatasetStorageError(
                "Dataset storage key is invalid."
            )

        path = Path(object_key)

        if path.is_absolute():
            raise DatasetStorageError(
                "Dataset storage keys must be relative."
            )

        raw_parts = object_key.split("/")

        if any(
            part in {"", ".", ".."}
            for part in raw_parts
        ):
            raise DatasetStorageError(
                "Dataset storage key contains an unsafe path component."
            )

        return path.as_posix()

    def _resolve_object_key(
        self,
        object_key: str,
    ) -> Path:
        normalized = self._normalize_object_key(
            object_key
        )

        candidate = (
            self.root_dir / normalized
        ).resolve()

        try:
            candidate.relative_to(
                self.root_dir
            )
        except ValueError as exc:
            raise DatasetStorageError(
                "Dataset storage key escapes the configured storage root."
            ) from exc

        return candidate

    def store_file(
        self,
        source_path: str | Path,
        object_key: str,
    ) -> str:
        source = (
            Path(source_path)
            .expanduser()
            .resolve()
        )

        if not source.is_file():
            raise FileNotFoundError(
                f"Dataset staging file not found: {source}"
            )

        normalized = self._normalize_object_key(
            object_key
        )
        destination = self._resolve_object_key(
            normalized
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Exclusive creation prevents accidental replacement of an
        # existing stored dataset object.
        with (
            source.open("rb") as source_file,
            destination.open("xb") as destination_file,
        ):
            shutil.copyfileobj(
                source_file,
                destination_file,
            )

        return normalized

    def reference_for_path(
        self,
        file_path: str | Path,
    ) -> str:
        """
        Return a portable relative reference when the file is inside
        the configured storage root.

        Paths outside the root remain absolute for backward-compatible
        tests and legacy local records.
        """
        path = (
            Path(file_path)
            .expanduser()
            .resolve()
        )

        try:
            relative = path.relative_to(
                self.root_dir
            )
        except ValueError:
            return str(path)

        return self._normalize_object_key(
            relative.as_posix()
        )

    def resolve_reference(
        self,
        reference: str,
    ) -> Path:
        if (
            not reference
            or "\x00" in reference
        ):
            raise DatasetStorageError(
                "Dataset storage reference is invalid."
            )

        reference_path = Path(reference)

        # Backward compatibility for DatasetVersion records created
        # before storage references became portable.
        if reference_path.is_absolute():
            return reference_path.expanduser().resolve()

        return self._resolve_object_key(
            reference
        )

    @contextmanager
    def materialize(
        self,
        reference: str,
    ) -> Iterator[Path]:
        path = self.resolve_reference(
            reference
        )

        if not path.is_file():
            raise FileNotFoundError(
                f"Stored dataset file not found: {reference}"
            )

        yield path

    def delete(
        self,
        reference: str,
    ) -> None:
        path = self.resolve_reference(
            reference
        )
        path.unlink(
            missing_ok=True
        )


def build_dataset_storage(settings) -> DatasetStorage:
    """
    Build the configured dataset storage backend.

    The S3 branch intentionally fails closed until the S3 adapter is
    implemented in Production Readiness 1C-B.
    """
    if settings.storage_backend == "local":
        return LocalDatasetStorage(
            settings.storage_local_root_path
        )

    if settings.storage_backend == "s3":
        raise RuntimeError(
            "S3 dataset storage is configured but the S3 adapter "
            "has not been initialized."
        )

    raise RuntimeError(
        f"Unsupported dataset storage backend: "
        f"{settings.storage_backend}"
    )
