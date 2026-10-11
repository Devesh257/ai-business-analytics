import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
import pandas as pd
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.api.dependencies import get_current_user, get_db
from app.models.dataset import Dataset, DatasetVersion
from app.models.user import User
from app.services.validator import validate_dataset
from app.security.pii_detector import analyze_pii
from app.services.profiler import profile_dataset
from app.services.semantic_detector import infer_semantics
from app.services.analysis_pipeline import run_phase1_analysis
from app.services.analytics_planner import build_analytics_plan


router = APIRouter(prefix="/datasets", tags=["Datasets"])

BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "storage" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def _safe_upload_filename(filename: str | None) -> str:
    if not filename or "\x00" in filename:
        raise HTTPException(status_code=400, detail="A valid filename is required.")

    if Path(filename).name != filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Unsafe filename.")

    if len(filename) > 255:
        raise HTTPException(status_code=400, detail="Filename is too long.")

    return filename


def _validate_uploaded_content(file_path: Path, extension: str) -> None:
    """Confirm that the uploaded bytes match the supported tabular format."""
    with file_path.open("rb") as uploaded_file:
        header = uploaded_file.read(8)

    if extension == ".xlsx" and not header.startswith(b"PK\x03\x04"):
        raise ValueError("The file content is not a valid XLSX workbook.")
    if extension == ".xls" and not header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise ValueError("The file content is not a valid XLS workbook.")

    try:
        if extension == ".csv":
            if b"\x00" in header:
                raise ValueError("The file content is not valid CSV text.")
            pd.read_csv(file_path, nrows=10)
        else:
            pd.read_excel(file_path, nrows=10)
    except Exception as exc:
        raise ValueError("The file content does not match its extension.") from exc


def _get_owned_dataset_version(
    db: Session,
    dataset_version_id: uuid.UUID,
    user_id: uuid.UUID,
) -> DatasetVersion:
    version = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.id == dataset_version_id,
            DatasetVersion.dataset.has(
                Dataset.user_id == user_id
            ),
        )
        .first()
    )

    if version is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset version not found.",
        )

    return version


# upload route

@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    dataset_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filename = _safe_upload_filename(file.filename)
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only CSV and Excel files are supported.",
        )

    file_id = uuid.uuid4()
    file_path = (UPLOAD_DIR / f"{file_id}{extension}").resolve()

    try:
        bytes_written = 0
        with file_path.open("xb") as buffer:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                bytes_written += len(chunk)
                if bytes_written > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Upload exceeds the 25 MB size limit.",
                    )
                buffer.write(chunk)

        _validate_uploaded_content(file_path, extension)
    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        if dataset_id is None:
            dataset = Dataset(
                id=uuid.uuid4(),
                user_id=current_user.id,
                name=Path(filename).stem,
            )
            db.add(dataset)
            db.flush()
            version_number = 1
        else:
            try:
                dataset_uuid = uuid.UUID(dataset_id)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid dataset_id.",
                ) from exc

            dataset = (
                db.query(Dataset)
                .filter(
                    Dataset.id == dataset_uuid,
                    Dataset.user_id == current_user.id,
                )
                .with_for_update()
                .first()
            )

            if dataset is None:
                raise HTTPException(
                    status_code=404,
                    detail="Dataset not found.",
                )

            latest_version = (
                db.query(DatasetVersion)
                .filter(DatasetVersion.dataset_id == dataset.id)
                .order_by(DatasetVersion.version_number.desc())
                .first()
            )
            version_number = latest_version.version_number + 1 if latest_version else 1

        version = DatasetVersion(
            id=file_id,
            dataset_id=dataset.id,
            version_number=version_number,
            file_name=filename,
            file_path=str(file_path),
        )
        db.add(version)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail="A dataset version conflict occurred. Please retry the upload.",
        ) from exc
    except Exception:
        db.rollback()
        file_path.unlink(missing_ok=True)
        raise

    return {
        "message": "Dataset uploaded successfully",
        "dataset_id": str(dataset.id),
        "dataset_version_id": str(file_id),
        "version_number": version_number,
        "file_name": filename,
    }

@router.get("")
def list_owned_datasets(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    owned_datasets = (
        db.query(Dataset)
        .options(
            selectinload(
                Dataset.versions
            )
        )
        .filter(
            Dataset.user_id
            == current_user.id
        )
        .order_by(
            Dataset.created_at.desc()
        )
        .all()
    )

    items = []

    for dataset in owned_datasets:
        versions = sorted(
            dataset.versions,
            key=lambda item: (
                item.version_number
            ),
            reverse=True,
        )

        latest = (
            versions[0]
            if versions
            else None
        )

        items.append(
            {
                "id": str(dataset.id),
                "name": dataset.name,
                "description": (
                    dataset.description
                ),
                "created_at": (
                    dataset.created_at
                ),
                "version_count": len(
                    versions
                ),
                "latest_version": (
                    {
                        "id": str(
                            latest.id
                        ),
                        "version_number": (
                            latest
                            .version_number
                        ),
                        "file_name": (
                            latest.file_name
                        ),
                        "created_at": (
                            latest.created_at
                        ),
                    }
                    if latest
                    else None
                ),
            }
        )

    return {
        "count": len(items),
        "datasets": items,
    }


@router.get(
    "/{dataset_id}/versions"
)
def list_owned_dataset_versions(
    dataset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    dataset = (
        db.query(Dataset)
        .options(
            selectinload(
                Dataset.versions
            )
        )
        .filter(
            Dataset.id == dataset_id,
            Dataset.user_id
            == current_user.id,
        )
        .first()
    )

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )

    versions = sorted(
        dataset.versions,
        key=lambda item: (
            item.version_number
        ),
        reverse=True,
    )

    return {
        "dataset_id": str(
            dataset.id
        ),
        "name": dataset.name,
        "count": len(versions),
        "versions": [
            {
                "id": str(
                    version.id
                ),
                "version_number": (
                    version.version_number
                ),
                "file_name": (
                    version.file_name
                ),
                "created_at": (
                    version.created_at
                ),
            }
            for version in versions
        ],
    }


# validate route
@router.post("/{dataset_version_id}/validate")
def validate_dataset_version(
    dataset_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = _get_owned_dataset_version(
        db,
        dataset_version_id,
        current_user.id,
    )

    try:
        validation_result = validate_dataset(
            version.file_path
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Validation failed: {str(e)}",
        )

    return {
        "dataset_version_id": str(
            dataset_version_id
        ),
        "validation": validation_result,
    }

# pii-scan route
@router.post("/{dataset_version_id}/pii-scan")
def scan_dataset_pii(
    dataset_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = _get_owned_dataset_version(
        db,
        dataset_version_id,
        current_user.id,
    )

    try:
        pii_result = analyze_pii(
            version.file_path
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"PII scan failed: {str(e)}",
        )

    return {
        "dataset_version_id": str(
            dataset_version_id
        ),
        "pii_scan": pii_result,
    }


# Profile
@router.get("/{dataset_version_id}/profile")
def profile_dataset_version(
    dataset_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = _get_owned_dataset_version(
        db,
        dataset_version_id,
        current_user.id,
    )

    try:
        pii_scan = analyze_pii(version.file_path)
        profile = profile_dataset(version.file_path, pii_scan["protected_columns"])
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Profiling failed: {str(e)}",
        )

    return {
        "dataset_version_id": str(
            dataset_version_id
        ),
        "profile": profile,
    }

# semantics
@router.get("/{dataset_version_id}/semantics")
def detect_dataset_semantics(
    dataset_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = _get_owned_dataset_version(
        db,
        dataset_version_id,
        current_user.id,
    )

    try:
        pii_scan = analyze_pii(version.file_path)
        semantics = infer_semantics(version.file_path, pii_scan["protected_columns"])
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Semantic detection failed: {str(e)}",
        )

    return {
        "dataset_version_id": str(
            dataset_version_id
        ),
        "semantics": semantics,
    }

# analyze
# analyze
@router.post("/{dataset_version_id}/analyze")
def analyze_dataset_version(
    dataset_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = _get_owned_dataset_version(
        db,
        dataset_version_id,
        current_user.id,
    )

    try:
        result = run_phase1_analysis(
            version.file_path,
            dataset_id=str(version.dataset_id),
            dataset_version_id=str(version.id),
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis failed: {str(e)}",
        )

    return {
        "analysis_run_id": result.get("analysis_run_id"),
        "dataset_version_id": str(dataset_version_id),
        "analysis": result,
    }

#plan
@router.get("/{dataset_version_id}/plan")
def create_analytics_plan(
    dataset_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = _get_owned_dataset_version(
        db,
        dataset_version_id,
        current_user.id,
    )

    try:
        pii_scan = analyze_pii(version.file_path)
        profile = profile_dataset(version.file_path, pii_scan["protected_columns"])

        semantics = infer_semantics(version.file_path, pii_scan["protected_columns"])

        plan = build_analytics_plan(
            profile,
            semantics,
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Planning failed: {str(e)}",
        )

    return {
        "dataset_version_id": str(
            dataset_version_id
        ),
        "analytics_plan": plan,
    }
