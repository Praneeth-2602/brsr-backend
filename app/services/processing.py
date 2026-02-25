import logging
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient

from ..config import settings
from .gemini_service import GeminiService
from . import storage_service


def process_document_job(document_id: str, file_url: str, prompt: str, user_id: str = None):
    """Worker job: download file from Supabase, call Gemini to extract JSON,
    and update MongoDB document record.

    This function is synchronous so it can be run by RQ workers.
    """
    try:
        # download file bytes from Supabase using the existing client
        try:
            # storage_service.supabase is the client created in storage_service
            path = file_url.split(f"/{storage_service.BUCKET_NAME}/")[1]
        except Exception:
            logging.exception("Invalid file URL: %s", file_url)
            path = None

        if not path:
            # update the db with failed status
            _update_doc(document_id, {"status": "failed", "error": "invalid_file_url", "parsed_at": datetime.utcnow()})
            return

        file_bytes = storage_service.supabase.storage.from_(storage_service.BUCKET_NAME).download(path)

        # call the existing async method synchronously
        try:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            parsed = loop.run_until_complete(GeminiService().extract_section_a(file_bytes, prompt))
        except Exception as exc:
            logging.exception("Extraction failed: %s", exc)
            _update_doc(document_id, {"status": "failed", "error": str(exc), "parsed_at": datetime.utcnow()})
            return
    except Exception as exc:
        logging.exception("Unexpected error processing document %s: %s", document_id, exc)
        _update_doc(document_id, {"status": "failed", "error": "unexpected_error", "parsed_at": datetime.utcnow()})
        return
    # Update MongoDB synchronously using pymongo
    _update_doc(document_id, {"status": "completed", "extracted_json": parsed, "parsed_at": datetime.utcnow()})


def _update_doc(document_id: str, update: dict):
    try:
        mc = MongoClient(settings.MONGO_URI)
        db = mc[settings.MONGO_DB]
        coll = db["documents"]
        coll.update_one({"_id": ObjectId(document_id)}, {"$set": update})
    except Exception:
        logging.exception("Failed to update document %s", document_id)
