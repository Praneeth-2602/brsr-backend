from supabase import create_client
from fastapi import HTTPException
from ..config import settings
import asyncio
import time
import logging

supabase = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_ROLE_KEY
)

BUCKET_NAME = getattr(settings, "SUPABASE_BUCKET", "pdfs")


def _sync_upload_with_retries(name: str, file_bytes: bytes, attempts: int = 3, backoff: float = 1.0):
    last_exc = None
    for i in range(attempts):
        try:
            supabase.storage.from_(BUCKET_NAME).upload(name, file_bytes)
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(name)
            if isinstance(public_url, dict):
                return public_url.get("publicURL") or public_url.get("publicUrl")
            return public_url
        except Exception as exc:
            last_exc = exc
            logging.exception("Supabase upload attempt %s failed for %s", i + 1, name)
            if i < attempts - 1:
                time.sleep(backoff * (2 ** i))
                continue
            raise last_exc


def _sync_download_with_retries(path: str, attempts: int = 3, backoff: float = 1.0):
    last_exc = None
    for i in range(attempts):
        try:
            return supabase.storage.from_(BUCKET_NAME).download(path)
        except Exception as exc:
            last_exc = exc
            logging.exception("Supabase download attempt %s failed for %s", i + 1, path)
            if i < attempts - 1:
                time.sleep(backoff * (2 ** i))
                continue
            raise last_exc


class StorageService:

    @staticmethod
    async def upload_file(file_bytes: bytes = None, filename: str = None, file_path: str = None, **kwargs) -> str:
        # Accept either positional `filename` or `file_path` keyword for compatibility
        name = filename or file_path or kwargs.get("file_path")
        if not name or file_bytes is None:
            raise HTTPException(status_code=400, detail="Missing file bytes or filename/file_path for upload")

        try:
            # run the blocking supabase upload in a threadpool and retry on transient failures
            public_url = await asyncio.to_thread(_sync_upload_with_retries, name, file_bytes)
        except Exception as exc:
            logging.exception("Failed to upload to Supabase: %s", exc)
            raise HTTPException(status_code=500, detail=f"Supabase storage error: {exc}")

        return public_url

    @staticmethod
    async def download_file(file_url: str) -> bytes:
        try:
            path = file_url.split(f"/{BUCKET_NAME}/")[1]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid file URL for download")

        try:
            data = await asyncio.to_thread(_sync_download_with_retries, path)
            return data
        except Exception as exc:
            logging.exception("Failed to download from Supabase: %s", exc)
            raise HTTPException(status_code=500, detail=f"Supabase download error: {exc}")