from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import upload, documents, excel, auth

app = FastAPI(title="BRSR PDF Parser Demo")

# CORS - allow all origins for frontend development
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(upload, prefix="/documents/upload", tags=["Upload"])
app.include_router(documents, prefix="/documents", tags=["Documents"])
app.include_router(excel, prefix="/documents/excel", tags=["Excel"])
app.include_router(auth, prefix="/auth", tags=["Auth"])


@app.get("/health", tags=["health"])
async def health_check():
	return {"status": "ok"}