"""Kimlik doğrulamalı medya servisi — tahmin edilebilir /media yollarını kapatır."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.admin_access import is_admin
from app.config import get_settings
from app.database import get_db
from app.models import User, VideoJob
from app.security import decode_access_token

router = APIRouter(tags=["media"])


def _user_from_access_token(access_token: str, db: Session) -> User:
    try:
        payload = decode_access_token(access_token)
        user_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz medya erişim jetonu",
        ) from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı yok")
    return user


@router.get("/media/jobs/{job_id}/{file_path:path}")
def get_job_media(
    job_id: int,
    file_path: str,
    access_token: str = Query(..., min_length=10),
    db: Session = Depends(get_db),
):
    user = _user_from_access_token(access_token, db)
    job = db.get(VideoJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İş yok")
    if job.user_id != user.id and not is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Erişim yok")

    root = (Path(get_settings().media_dir) / "jobs" / str(job_id)).resolve()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dosya yok")

    return FileResponse(target)


def _media_base() -> Path:
    root = Path(get_settings().media_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent.parent.parent / root
    return root.resolve()


@router.get("/media/uploads/{user_id}/{file_path:path}")
def get_upload_media(
    user_id: int,
    file_path: str,
    access_token: str = Query(..., min_length=10),
    db: Session = Depends(get_db),
):
    user = _user_from_access_token(access_token, db)
    if user.id != user_id and not is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Erişim yok")
    root = (_media_base() / "uploads" / str(user_id)).resolve()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dosya yok")
    return FileResponse(target)


@router.get("/media/creative/{user_id}/{job_id}/{file_path:path}")
def get_creative_media(
    user_id: int,
    job_id: str,
    file_path: str,
    access_token: str = Query(..., min_length=10),
    db: Session = Depends(get_db),
):
    user = _user_from_access_token(access_token, db)
    if user.id != user_id and not is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Erişim yok")
    root = (_media_base() / "creative" / str(user_id) / job_id).resolve()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dosya yok")
    return FileResponse(target)
