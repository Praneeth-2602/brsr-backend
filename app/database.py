from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from .config import settings

_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
	"""Lazily create and return the Motor client.

	This avoids parsing the MONGO_URI at import time and makes startup
	resilient to temporarily-misconfigured environment variables.
	"""
	global _client
	if _client is None:
		if not settings.MONGO_URI:
			raise RuntimeError("MONGO_URI not configured in environment")
		_client = AsyncIOMotorClient(settings.MONGO_URI)
	return _client


def get_db():
	client = get_client()
	return client[settings.MONGO_DB]


# Convenience: collection accessor used across the app. Importing this module
# will NOT create a client until `get_client()` or `get_db()` is called.
def documents_collection():
	return get_db()["documents"]