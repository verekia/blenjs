"""Stable UUID identity for objects (spec §6.6).

Every object gets a ``blenjs_uuid`` *custom property* (an ID-property), generated
lazily on first touch. The YAML key *is* this UUID — identity is never by name,
because Blender renames objects freely.

Identity MUST live in one storage namespace. We use the ID-property API
(``obj["blenjs_uuid"]`` / ``obj.get("blenjs_uuid")``) everywhere. Do not register
``blenjs_uuid`` as an RNA ``StringProperty`` and assign it via the attribute
(``obj.blenjs_uuid = ...``): in Blender those are a *separate* store that
``obj.get()`` cannot see, so ``ensure_uuid`` would never read back what it wrote
and would mint a fresh UUID on every call — entity keys and entity-refs then
disagree and the runtime rejects the scene with "Unresolved entity references".
"""

import uuid as _uuid


def new_uuid() -> str:
    return _uuid.uuid4().hex


def ensure_uuid(obj) -> str:
    existing = obj.get("blenjs_uuid", "")
    if not existing:
        existing = new_uuid()
        obj["blenjs_uuid"] = existing
    return existing
