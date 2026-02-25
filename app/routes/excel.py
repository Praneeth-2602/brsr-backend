from fastapi import APIRouter, Depends
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

    coll = documents_collection()
    docs = coll.find({
        "_id": {"$in": [ObjectId(i) for i in request.document_ids]},
        "user_id": user["sub"],
        "status": "completed"
    })

    json_docs = []
    async for d in docs:
        json_docs.append(d["extracted_json"])

    excel_file = ExcelService.generate_excel(json_docs)

    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=section_a.xlsx"}
    )