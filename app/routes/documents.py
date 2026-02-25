from fastapi import APIRouter, Depends
from typing import Optional

from ..bson_compat import ObjectId
from ..auth import get_current_user
from ..database import documents_collection
from ..models import DocumentStatusRequest

router = APIRouter()


@router.get("/")
async def list_documents(user=Depends(get_current_user)):
    coll = documents_collection()
    docs = coll.find({"user_id": user["sub"]})

    results = []
    async for d in docs:
        d["id"] = str(d["_id"])
        del d["_id"]
        results.append(d)

    return results


@router.get("/{doc_id}")
async def get_document(doc_id: str, user=Depends(get_current_user)):
    coll = documents_collection()
    doc = await coll.find_one({
        "_id": ObjectId(doc_id),
        "user_id": user["sub"]
    })

    if doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]

    return doc


@router.post("/status")
async def documents_status(request: Optional[DocumentStatusRequest] = None, user=Depends(get_current_user)):
    """Return status summary for documents belonging to the current user.

    If `document_ids` are provided in the request body, return those documents.
    If no body is provided (or `document_ids` is empty), return all documents for the user.

    Returns a list of objects: {id, status, error_message, parsed_at, file_url}.
    """
    coll = documents_collection()

    # If a list of ids was provided, filter by them; otherwise return all for the user
    if request and getattr(request, "document_ids", None):
        try:
            ids = [ObjectId(i) for i in request.document_ids]
        except Exception:
            return {"error": "one or more invalid document ids"}
        cursor = coll.find({"_id": {"$in": ids}, "user_id": user["sub"]})
    else:
        cursor = coll.find({"user_id": user["sub"]})

    out = []
    async for d in cursor:
        out.append({
            "id": str(d["_id"]),
            "status": d.get("status"),
            "error_message": d.get("error_message"),
            "parsed_at": d.get("parsed_at"),
            "file_url": d.get("file_url"),
        })

    return out