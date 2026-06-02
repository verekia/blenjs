"""JSON load + canonical export for BlenJS.

This module is intentionally free of any ``bpy`` import so the canonicalization
logic can be unit-tested outside Blender (see ``blender/tests/test_roundtrip.py``).
The Blender save path (``scenes.py``) builds a plain data dict from datablocks and
hands it to :func:`canonical_json` here.

Canonical form (spec §6.8):
  * top-level key order: ``version`` then ``scenes``
  * scenes sorted (natural order); entities sorted by UUID
  * per-entity key order: ``name``, ``Transform``, then other components alpha
  * per-component fields in *schema order*, every field emitted (defaults filled)
  * horizontally compact layout: structure (scenes / entities / entity) is broken
    onto its own lines, while leaves (whole components inline, vectors inline) stay
    on one line — e.g. ``"Transform": {"pos": [9, 0, 0], ...}`` — so XYZ triples and
    small components read on a single row. A leaf only ever wraps when it would
    push a line past :data:`MAX_WIDTH` (120) characters.
  * floats quantized to 4 decimals; whole numbers collapse to ``int`` (so ``1.0``
    becomes ``1`` — JSON has no ``1.0`` vs ``"1.0"`` ambiguity, but this keeps the
    bytes stable and the file tidy)

We hand-roll the serializer (stdlib ``json`` can pretty-print *or* compact, but not
this hybrid "dense leaves, broken structure" layout) so flow/block presentation is
fully under our control and byte-stable. Parsing is plain ``json.loads`` — no third
party dependency, which is the whole point of moving off YAML.
"""

from __future__ import annotations

import json
from typing import Any

QUANT_DIGITS = 4
MAX_WIDTH = 120  # a leaf wraps onto multiple lines only if inlining would exceed this
INDENT = 2


# --------------------------------------------------------------------------- #
# Schema contract
# --------------------------------------------------------------------------- #
class Schema:
    """Thin reader over ``generated/components.schema.json``."""

    def __init__(self, doc: dict[str, Any]):
        self.version: int = int(doc.get("schemaVersion", 0))
        self.components: dict[str, dict[str, Any]] = {c["name"]: c for c in doc.get("components", [])}

    @classmethod
    def load(cls, path: str) -> "Schema":
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f))

    def has(self, comp: str) -> bool:
        return comp in self.components

    def fields(self, comp: str) -> list[dict[str, Any]]:
        return self.components.get(comp, {}).get("fields", [])

    def field_order(self, comp: str) -> list[str]:
        return [f["name"] for f in self.fields(comp)]

    def field(self, comp: str, name: str) -> dict[str, Any] | None:
        for f in self.fields(comp):
            if f["name"] == name:
                return f
        return None

    def default(self, comp: str, name: str) -> Any:
        f = self.field(comp, name)
        if f is None:
            return None
        if "default" in f:
            return f["default"]
        # Synthesize a sensible default for required (no-default) fields, mirroring
        # what Blender's PropertyGroup would surface.
        t = f.get("type")
        if t == "enum":
            vals = f.get("enumValues") or [""]
            return vals[0]
        if t in ("number", "int"):
            return f.get("min", 0)
        if t == "bool":
            return False
        if t in ("vec2", "vec3", "vec4"):
            n = int(t[-1])
            return [0.0] * n
        if t == "array":
            return []
        return ""


# --------------------------------------------------------------------------- #
# Value canonicalization
# --------------------------------------------------------------------------- #
def quantize(x: Any) -> Any:
    """Round numbers to QUANT_DIGITS; collapse whole numbers to int."""
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        r = round(float(x), QUANT_DIGITS)
        if r == int(r):
            return int(r)
        return r
    return x


def _seq(values: list[Any], *, quant: bool) -> list[Any]:
    return [quantize(v) if quant else (str(v) if not isinstance(v, bool) else v) for v in values]


def _value_for_field(field: dict[str, Any], val: Any) -> Any:
    t = field.get("type")
    if t in ("vec2", "vec3", "vec4"):
        n = int(t[-1])
        seq = list(val) if isinstance(val, (list, tuple)) else [0] * n
        seq = (seq + [0] * n)[:n]
        return _seq(seq, quant=True)
    if t == "array":
        items = list(val) if isinstance(val, (list, tuple)) else []
        # entityRef / string arrays are not quantized; numeric arrays are.
        numeric = field.get("itemType") in ("number", "int")
        return _seq(items, quant=numeric)
    if t == "int":
        return int(round(float(val))) if isinstance(val, (int, float)) else int(val)
    if t == "number":
        return quantize(val)
    if t == "bool":
        return bool(val)
    # enum / string / entityRef
    return str(val)


def _component(comp: str, data: dict[str, Any], schema: Schema) -> dict[str, Any]:
    out: dict[str, Any] = {}
    src = data or {}
    for fname in schema.field_order(comp):
        field = schema.field(comp, fname)
        raw = src.get(fname, schema.default(comp, fname))
        out[fname] = _value_for_field(field or {}, raw)
    return out


def _generic_component(data: Any) -> dict[str, Any]:
    """Fallback for an unknown component: keep the data, quantized."""
    out: dict[str, Any] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (list, tuple)):
                out[k] = _seq(list(v), quant=True)
            else:
                out[k] = quantize(v)
    return out


def _entity(uuid: str, ent: dict[str, Any], schema: Schema) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = str(ent.get("name", uuid))

    comp_keys = [k for k in ent.keys() if k != "name"]
    ordered: list[str] = []
    if "Transform" in comp_keys:
        ordered.append("Transform")
    ordered += sorted(k for k in comp_keys if k != "Transform")

    for k in ordered:
        if schema.has(k):
            out[k] = _component(k, ent.get(k) or {}, schema)
        else:
            out[k] = _generic_component(ent.get(k) or {})
    return out


def _natkey(s: str) -> list[Any]:
    import re

    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(s))]


def canonicalize(data: dict[str, Any], schema: Schema) -> dict[str, Any]:
    """Rebuild ``data`` into a canonical, byte-stable plain-dict structure."""
    root: dict[str, Any] = {}
    root["version"] = int(data.get("version", schema.version))

    scenes_out: dict[str, Any] = {}
    scenes_src = data.get("scenes") or {}
    for sname in sorted(scenes_src.keys(), key=_natkey):
        scene = scenes_src.get(sname) or {}
        ents_src = scene.get("entities") or {}
        ents_out: dict[str, Any] = {}
        for uuid in sorted(ents_src.keys()):
            ents_out[uuid] = _entity(uuid, ents_src.get(uuid) or {}, schema)
        scenes_out[sname] = {"entities": ents_out}

    root["scenes"] = scenes_out
    return root


# --------------------------------------------------------------------------- #
# Serialization — hybrid "dense leaves, broken structure" pretty-printer
# --------------------------------------------------------------------------- #
def _is_scalar(x: Any) -> bool:
    return isinstance(x, (str, int, float, bool)) or x is None


def _inlinable(v: Any) -> bool:
    """A container is a *leaf* (kept on one line) only if it has no nested container.

    Components like ``{"pos": [9, 0, 0], "rot": [...]}`` qualify (their values are
    scalars or flat scalar lists); an entity ``{"name": ..., "Transform": {...}}``
    does not (it holds nested objects), so structure always breaks onto its own
    lines while leaves stay dense.
    """
    if isinstance(v, dict):
        return all(_is_scalar(x) or _is_scalar_list(x) for x in v.values())
    if isinstance(v, list):
        return all(_is_scalar(x) for x in v)
    return True


def _is_scalar_list(x: Any) -> bool:
    return isinstance(x, list) and all(_is_scalar(i) for i in x)


def _inline(v: Any) -> str:
    """Compact single-line JSON: ``{"pos": [9, 0, 0], "rot": [0, 0, 0]}``."""
    return json.dumps(v, ensure_ascii=False)


def _dump(v: Any, line_indent: int, col: int) -> str:
    """Render ``v`` starting at column ``col``; if it must break, child lines are
    indented from ``line_indent``. Leaves stay inline unless they'd pass MAX_WIDTH."""
    if _inlinable(v):
        s = _inline(v)
        if col + len(s) <= MAX_WIDTH:
            return s

    if isinstance(v, dict):
        if not v:
            return "{}"
        child_indent = line_indent + INDENT
        pad = " " * child_indent
        parts = []
        for k, val in v.items():
            key = json.dumps(k, ensure_ascii=False)
            prefix = f"{pad}{key}: "
            parts.append(prefix + _dump(val, child_indent, len(prefix)))
        return "{\n" + ",\n".join(parts) + "\n" + " " * line_indent + "}"

    if isinstance(v, list):
        if not v:
            return "[]"
        child_indent = line_indent + INDENT
        pad = " " * child_indent
        parts = [pad + _dump(x, child_indent, child_indent) for x in v]
        return "[\n" + ",\n".join(parts) + "\n" + " " * line_indent + "]"

    return _inline(v)


def loads(text: str) -> dict[str, Any]:
    data = json.loads(text) if text.strip() else None
    return data if data is not None else {}


def load_file(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return loads(f.read())


def dumps(node: Any) -> str:
    return _dump(node, 0, 0) + "\n"


def canonical_json(data: dict[str, Any], schema: Schema) -> str:
    """Full pipeline: raw data dict -> canonical, compact JSON string."""
    return dumps(canonicalize(data, schema))
