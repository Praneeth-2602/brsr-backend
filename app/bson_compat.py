"""Compatibility shim for `bson` imports across environments.

Ensures `ObjectId` and `SON` are available even if the installed `bson`
package layout differs (some environments install a namespace package
without __init__.py). Import this module instead of importing directly
from `bson` to avoid ImportError at runtime.
"""
from collections import OrderedDict

try:
    # Preferred: pymongo's bundled bson
    from bson import ObjectId, SON  # type: ignore
except Exception:
    try:
        # Try explicit submodules
        from bson.objectid import ObjectId  # type: ignore
    except Exception:
        try:
            # Last resort: pymongo internals
            from pymongo.objectid import ObjectId  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise ImportError("ObjectId not available from bson or pymongo") from exc

    try:
        from bson.son import SON  # type: ignore
    except Exception:
        SON = OrderedDict

__all__ = ["ObjectId", "SON"]
