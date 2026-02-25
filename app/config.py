import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB = os.getenv("MONGO_DB", "brsr_demo")

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "pdfs")

    # JWT verification settings (used when validating Supabase tokens)
    SUPABASE_JWT_AUD = os.getenv("SUPABASE_JWT_AUD", "authenticated")
    SUPABASE_JWT_ISSUER = os.getenv("SUPABASE_JWT_ISSUER", "")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    # Local JWT settings for demo auth (optional). If not provided, local auth is disabled.
    local_jwt_secret: str = os.getenv("LOCAL_JWT_SECRET", "")
    local_jwt_algorithm: str = os.getenv("LOCAL_JWT_ALGORITHM", "HS256")
    local_jwt_exp_minutes: int = int(os.getenv("LOCAL_JWT_EXP_MINUTES", "1440"))

settings = Settings()


def get_settings() -> Settings:
    """Backward-compatible accessor used by other modules."""
    return settings