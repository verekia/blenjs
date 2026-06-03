"""Prefab manifest (``generated/prefabs.json``) loading + resolution for the add-on.

Mirrors the runtime ``resolvePrefabs``: a .blen.json entity with a ``prefab`` key
inherits the prefab's components, overlaid per-field by the instance's own overrides.
Used to (a) visualize an instance with its real, *resolved* transform/data on import
and (b) diff back to a sparse override set on export (see ``scenes.build_data``).

No ``bpy`` import (stdlib only) so it stays unit-testable outside Blender.
"""

import json
import os

# Entity-level keys that are not components.
RESERVED = ("name", "prefab")

_prefabs: "dict | None" = None  # cached manifest: {name: {"name", "components"}}


def load(path: "str | None") -> dict:
    """Load the prefab manifest from a PROJECT path (``<root>/generated/prefabs.json``).
    A missing file yields an empty manifest, so prefab instances fall back to placeholders."""
    global _prefabs
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            _prefabs = json.load(f) or {}
        print(f"[blenjs] loaded {len(_prefabs)} prefab(s) from {path}")
    else:
        print(f"[blenjs] prefabs.json not found at {path} — run `bun run build:models` (instances show as placeholders).")
        _prefabs = {}
    return _prefabs


def get() -> dict:
    return _prefabs if _prefabs is not None else {}


def definition(name: str) -> "dict | None":
    return get().get(name)


def resolve_components(prefab_name: str, instance: dict) -> dict:
    """Merge a prefab's components with an instance's overrides (per field, instance
    wins). Returns ``{component: {field: value}}`` — the resolved entity body (no
    ``name``/``prefab``). An unknown prefab resolves to the instance's own overrides.
    """
    pdef = get().get(prefab_name) or {}
    merged: dict = {}
    for cname, cdata in (pdef.get("components") or {}).items():
        merged[cname] = dict(cdata)
    for key, val in (instance or {}).items():
        if key in RESERVED:
            continue
        if isinstance(val, dict):
            base = dict(merged.get(key) or {})
            base.update(val)
            merged[key] = base
        else:
            merged[key] = val
    return merged
