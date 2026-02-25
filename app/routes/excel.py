from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from ..bson_compat import ObjectId
from ..auth import get_current_user
from ..database import documents_collection
from ..services.excel_service import ExcelService
from ..models import ExcelRequest

router = APIRouter()


@router.post("/")
@router.post("")
async def generate_excel(request: ExcelRequest, user=Depends(get_current_user)):
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="document_ids is required")

    try:
        object_ids = [ObjectId(i) for i in request.document_ids]
    except Exception:
        raise HTTPException(status_code=400, detail="one or more invalid document_ids")

    coll = documents_collection()
    docs = coll.find({
        "_id": {"$in": object_ids},
        "user_id": user["sub"],
        "status": "completed",
        "extracted_json": {"$exists": True, "$ne": None},
    })

    by_id = {}
    async for d in docs:
        by_id[str(d["_id"])] = d.get("extracted_json")

    # Preserve caller order and include only requested IDs that matched
    json_docs = [by_id[doc_id] for doc_id in request.document_ids if doc_id in by_id]

    if not json_docs:
        raise HTTPException(
            status_code=404,
            detail="No completed documents found for the provided document_ids",
        )

    excel_file = ExcelService.generate_excel(json_docs)

    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=section_a.xlsx"}
    )
