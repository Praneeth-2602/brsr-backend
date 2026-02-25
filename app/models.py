from datetime import datetime
from typing import Any, List, Optional

from .bson_compat import ObjectId
from pydantic import BaseModel, Field


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):  # type: ignore[override]
        if isinstance(v, ObjectId):
            return v
        try:
            return ObjectId(str(v))
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Not a valid ObjectId") from exc


class DocumentStatus:
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentCreate(BaseModel):
    file_name: str
    file_url: str
    user_id: str
    status: str = DocumentStatus.PROCESSING
    extracted_json: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    parsed_at: Optional[datetime] = None


class DocumentInDB(DocumentCreate):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        validate_by_name = True
        json_encoders = {ObjectId: str}


class DocumentListItem(BaseModel):
    id: str
    file_name: str
    status: str
    created_at: datetime
    parsed_at: Optional[datetime]


class DocumentDetail(BaseModel):
    id: str
    file_name: str
    status: str
    extracted_json: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime
    parsed_at: Optional[datetime]


class ExcelRequest(BaseModel):
    document_ids: List[str]


class DocumentStatusRequest(BaseModel):
    document_ids: List[str]