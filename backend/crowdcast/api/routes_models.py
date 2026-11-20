"""Model registry endpoints (doc 14 §2, §3.15; WORKFLOW 5.3.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from crowdcast.api.deps import SessionDep
from crowdcast.api.errors import ApiError
from crowdcast.common.config import REPO_ROOT
from crowdcast.forecasting.features import FeatureSet
from crowdcast.forecasting.xgb import artifacts_complete
from crowdcast.storage.interfaces import ModelVersion, repository

router = APIRouter(prefix="/api/models", tags=["models"])

LOADABLE_FAMILIES = {"XGBOOST"}  # families the online cycle can run (doc 10 §12)


class ModelOut(BaseModel):
    model_version_id: int
    name: str
    version: str
    model_family: str
    feature_set: str | None
    is_active: bool
    created_at: datetime
    metrics: dict[str, Any] | None


class ModelList(BaseModel):
    models: list[ModelOut]


class Activation(BaseModel):
    model_version_id: int
    is_active: bool
    previous_active: int | None


def _out(m: ModelVersion) -> ModelOut:
    return ModelOut(
        model_version_id=m.model_version_id,
        name=m.name,
        version=m.version,
        model_family=m.model_family,
        feature_set=m.feature_set,
        is_active=m.is_active,
        created_at=m.created_at,
        metrics=m.metrics,
    )


@router.get("", response_model=ModelList)
def list_models(session: SessionDep) -> ModelList:
    rows = session.scalars(select(ModelVersion).order_by(ModelVersion.model_version_id.desc()))
    return ModelList(models=[_out(m) for m in rows])


@router.post("/{model_version_id}/activate", response_model=Activation)
def activate(model_version_id: int, session: SessionDep) -> Activation:
    """Make one model the active forecaster; the previous one is deactivated (doc 14 §3.15)."""
    model = session.get(ModelVersion, model_version_id)
    if model is None:
        raise ApiError(404, "NOT_FOUND", f"model version {model_version_id} not found")
    if model.model_family not in LOADABLE_FAMILIES:
        raise ApiError(
            422, "VALIDATION_ERROR", f"model family {model.model_family} cannot be activated"
        )
    if model.feature_set not in {fs.value for fs in FeatureSet}:
        raise ApiError(422, "VALIDATION_ERROR", f"feature set {model.feature_set} not supported")
    missing = artifacts_complete(REPO_ROOT / model.artifact_path)
    if missing:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "model artefacts missing",
            [{"field": "artifact_path", "issue": f"missing {f}"} for f in missing],
        )
    previous = repository.active_model_version(session)
    if previous is not None and previous.model_version_id != model.model_version_id:
        previous.is_active = False
        session.flush()  # the partial unique index allows one active model at a time
    model.is_active = True
    repository.add_audit(
        session,
        "MODEL_ACTIVATE",
        "model_version",
        model.model_version_id,
        {"previous_active": None if previous is None else previous.model_version_id},
        actor="USER",
    )
    session.flush()
    return Activation(
        model_version_id=model.model_version_id,
        is_active=True,
        previous_active=None if previous is None else previous.model_version_id,
    )
