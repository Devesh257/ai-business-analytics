from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.analysis import AnalysisRun
from app.models.dataset import Dataset, DatasetVersion
from app.models.user import User
from app.services.report_exporter import (
    build_csv_export,
    build_pdf_export,
    build_xlsx_export,
)

router = APIRouter(prefix="/analysis-runs", tags=["Analysis Runs"])


def _get_owned_analysis_run(
    db: Session,
    analysis_run_id: UUID,
    user_id: UUID,
) -> AnalysisRun:
    analysis_run = (
        db.query(AnalysisRun)
        .filter(
            AnalysisRun.id == analysis_run_id,
            AnalysisRun.dataset_version.has(
                DatasetVersion.dataset.has(
                    Dataset.user_id == user_id
                )
            ),
        )
        .first()
    )

    if analysis_run is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis run not found",
        )

    return analysis_run


def _get_owned_dataset_version(
    db: Session,
    dataset_version_id: UUID,
    user_id: UUID,
) -> DatasetVersion:
    dataset_version = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.id == dataset_version_id,
            DatasetVersion.dataset.has(
                Dataset.user_id == user_id
            ),
        )
        .first()
    )

    if dataset_version is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset version not found",
        )

    return dataset_version


@router.get("/{analysis_run_id}")
def get_analysis_run(
    analysis_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis_run = _get_owned_analysis_run(
        db,
        analysis_run_id,
        current_user.id,
    )

    return {
        "id": str(analysis_run.id),
        "dataset_version_id": str(analysis_run.dataset_version_id),
        "status": analysis_run.status,
        "validation_result": analysis_run.validation_result,
        "pii_result": analysis_run.pii_result,
        "profile_result": analysis_run.profile_result,
        "semantic_result": analysis_run.semantic_result,
        "plan_result": analysis_run.plan_result,
        "analysis_results": analysis_run.analysis_results,
        "discovered_insights": analysis_run.discovered_insights,
        "verified_insights": analysis_run.verified_insights,
        "confidence_insights": analysis_run.confidence_insights,
        "scored_insights": analysis_run.scored_insights,
        "ranked_insights": analysis_run.ranked_insights,
        "created_at": analysis_run.created_at,
        "explained_insights": analysis_run.explained_insights,
        "recommended_insights": analysis_run.recommended_insights,
    }


@router.get("/{analysis_run_id}/export/{export_format}")
def export_analysis_run(
    analysis_run_id: UUID,
    export_format: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis_run = _get_owned_analysis_run(
        db,
        analysis_run_id,
        current_user.id,
    )

    export_format = (
        export_format
        .strip()
        .lower()
    )

    base_filename = (
        f"signal-ledger-"
        f"{analysis_run.id}"
    )

    if export_format == "csv":
        content = build_csv_export(
            analysis_run.ranked_insights,
            analysis_run.explained_insights,
            analysis_run.recommended_insights,
        )

        return Response(
            content=content,
            media_type=(
                "text/csv; "
                "charset=utf-8"
            ),
            headers={
                "Content-Disposition": (
                    f'attachment; filename="'
                    f'{base_filename}.csv"'
                ),
                "X-Export-Scope": (
                    "ranked-verified-insights"
                ),
            },
        )

    if export_format == "xlsx":
        content = build_xlsx_export(
            run_id=analysis_run.id,
            dataset_version_id=(
                analysis_run
                .dataset_version_id
            ),
            status=analysis_run.status,
            created_at=(
                analysis_run.created_at
            ),
            ranked_insights=(
                analysis_run
                .ranked_insights
            ),
            explained_insights=(
                analysis_run
                .explained_insights
            ),
            recommended_insights=(
                analysis_run
                .recommended_insights
            ),
        )

        return Response(
            content=content,
            media_type=(
                "application/"
                "vnd.openxmlformats-"
                "officedocument."
                "spreadsheetml.sheet"
            ),
            headers={
                "Content-Disposition": (
                    f'attachment; filename="'
                    f'{base_filename}.xlsx"'
                ),
                "X-Export-Scope": (
                    "ranked-verified-insights"
                ),
            },
        )

    if export_format == "pdf":
        content = build_pdf_export(
            run_id=analysis_run.id,
            dataset_version_id=(
                analysis_run
                .dataset_version_id
            ),
            status=analysis_run.status,
            created_at=(
                analysis_run.created_at
            ),
            ranked_insights=(
                analysis_run
                .ranked_insights
            ),
            explained_insights=(
                analysis_run
                .explained_insights
            ),
            recommended_insights=(
                analysis_run
                .recommended_insights
            ),
        )

        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="'
                    f'{base_filename}.pdf"'
                ),
                "X-Export-Scope": (
                    "ranked-verified-insights"
                ),
            },
        )

    raise HTTPException(
        status_code=400,
        detail=(
            "Unsupported export format. "
            "Use csv, xlsx, or pdf."
        ),
    )





@router.get("/dataset-version/{dataset_version_id}")
def get_analysis_runs_for_dataset_version(
    dataset_version_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset_version = _get_owned_dataset_version(
        db,
        dataset_version_id,
        current_user.id,
    )

    analysis_runs = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.dataset_version_id == dataset_version_id)
        .order_by(AnalysisRun.created_at.desc())
        .all()
    )

    return {
        "dataset_version_id": str(dataset_version_id),
        "count": len(analysis_runs),
        "analysis_runs": [
            {
                "id": str(run.id),
                "status": run.status,
                "created_at": run.created_at,
            }
            for run in analysis_runs
        ],
    }