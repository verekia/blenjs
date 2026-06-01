"""Stable UUID identity for objects (spec §6.6).

Every object gets a ``blenjs_uuid`` custom property, generated lazily on first
touch. The YAML key *is* this UUID — identity is never by name, because Blender
renames objects freely.
"""

import uuid as _uuid


def new_uuid() -> str:
    return _uuid.uuid4().hex


def ensure_uuid(obj) -> str:
    existing = obj.get("blenjs_uuid", "")
    if not existing:
        existing = new_uuid()
        obj.blenjs_uuid = existing
    return existing
