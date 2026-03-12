"""Settings router for runtime configuration overrides."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.config import (
    EDITABLE_SETTINGS,
    SENSITIVE_SETTINGS,
    get_env_setting_value,
    get_setting_metadata,
    serialize_override_value,
    settings,
)
from app.database import get_db
from app.schemas import AppSettingResponse, AppSettingUpdate

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=list[AppSettingResponse])
def list_settings(db: Session = Depends(get_db)):
    """Return effective settings, with source showing env vs db override."""
    overrides = {
        row.key: row
        for row in db.query(models.AppSetting).all()
    }

    response: list[AppSettingResponse] = []
    for meta in get_setting_metadata():
        key = meta["key"]
        source = "db" if key in overrides else "env"
        response.append(
            AppSettingResponse(
                key=key,
                type=meta["type"],
                sensitive=meta["sensitive"],
                value=getattr(settings, key),
                default_value=meta["default_value"],
                source=source,
            )
        )

    return response


@router.put("/settings/{setting_key}", response_model=AppSettingResponse)
def upsert_setting(
    setting_key: str,
    payload: AppSettingUpdate,
    db: Session = Depends(get_db),
):
    """Create or update a DB override for one setting key."""
    if setting_key not in EDITABLE_SETTINGS:
        raise HTTPException(status_code=400, detail="Unsupported setting key")

    default_value = get_env_setting_value(setting_key)
    try:
        serialized = serialize_override_value(payload.value, default_value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    value_type = (
        "boolean"
        if isinstance(default_value, bool)
        else "integer"
        if isinstance(default_value, int)
        else "number"
        if isinstance(default_value, float)
        else "string"
    )

    row = db.query(models.AppSetting).filter(
        models.AppSetting.key == setting_key
    ).first()
    if row is None:
        row = models.AppSetting(
            key=setting_key,
            value=serialized,
            value_type=value_type,
        )
        db.add(row)
    else:
        row.value = serialized
        row.value_type = value_type

    db.commit()
    settings.invalidate_cache()

    return AppSettingResponse(
        key=setting_key,
        type=value_type,
        sensitive=setting_key in SENSITIVE_SETTINGS,
        value=getattr(settings, setting_key),
        default_value=default_value,
        source="db",
    )


@router.delete("/settings/{setting_key}", response_model=AppSettingResponse)
def delete_setting_override(setting_key: str, db: Session = Depends(get_db)):
    """Delete DB override and fall back to .env value."""
    if setting_key not in EDITABLE_SETTINGS:
        raise HTTPException(status_code=400, detail="Unsupported setting key")

    row = db.query(models.AppSetting).filter(
        models.AppSetting.key == setting_key
    ).first()
    if row:
        db.delete(row)
        db.commit()

    settings.invalidate_cache()

    default_value = get_env_setting_value(setting_key)
    value_type = (
        "boolean"
        if isinstance(default_value, bool)
        else "integer"
        if isinstance(default_value, int)
        else "number"
        if isinstance(default_value, float)
        else "string"
    )

    return AppSettingResponse(
        key=setting_key,
        type=value_type,
        sensitive=setting_key in SENSITIVE_SETTINGS,
        value=default_value,
        default_value=default_value,
        source="env",
    )
