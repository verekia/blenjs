"""YAML load + canonical export for BlenJS.

This module is intentionally free of any ``bpy`` import so the canonicalization
logic can be unit-tested outside Blender (see ``blender/tests/test_roundtrip.py``).
The Blender save path (``scenes.py``) builds a plain data dict from datablocks and
hands it to :func:`canonical_yaml` here.

Canonical form (spec §6.8):
  * top-level key order: ``version`` then ``scenes``
  * scenes sorted (natural order); entities sorted by UUID
  * per-entity key order: ``name``, ``Transform``, then other components alpha
  * per-component fields in *schema order*, every field emitted (defaults filled)
  * block style for structure (scenes / entities / entity), flow style for leaves
    (whole components inline, vectors inline)
  * floats quantized to 4 decimals; whole numbers collapse to ``int`` (so ``1.0``
    becomes ``1`` — the canonical answer to YAML's ``1.0`` vs ``"1.0"`` ambiguity)

Comments on data are NOT preserved through canonicalization: the Blender save path
rebuilds YAML from datablocks, which never carried comments. ruamel is still used
so flow/block presentation is fully under our control and byte-stable.
"""

from __future__ import annotations

import io
import re
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

QUANT_DIGITS = 4


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
        import json

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


def _flow_seq(values: list[Any], *, quant: bool) -> CommentedSeq:
    cs = CommentedSeq(quantize(v) if quant else (str(v) if not isinstance(v, bool) else v) for v in values)
    cs.fa.set_flow_style()
    return cs


def _value_for_field(field: dict[str, Any], val: Any) -> Any:
    t = field.get("type")
    if t in ("vec2", "vec3", "vec4"):
        n = int(t[-1])
        seq = list(val) if isinstance(val, (list, tuple)) else [0] * n
        seq = (seq + [0] * n)[:n]
        return _flow_seq(seq, quant=True)
    if t == "array":
        items = list(val) if isinstance(val, (list, tuple)) else []
        # entityRef / string arrays are not quantized; numeric arrays are.
        numeric = field.get("itemType") in ("number", "int")
        return _flow_seq(items, quant=numeric)
    if t == "int":
        return int(round(float(val))) if isinstance(val, (int, float)) else int(val)
    if t == "number":
        return quantize(val)
    if t == "bool":
        return bool(val)
    # enum / string / entityRef
    return str(val)


def _component(comp: str, data: dict[str, Any], schema: Schema) -> CommentedMap:
    cm = CommentedMap()
    src = data or {}
    for fname in schema.field_order(comp):
        field = schema.field(comp, fname)
        raw = src.get(fname, schema.default(comp, fname))
        cm[fname] = _value_for_field(field or {}, raw)
    cm.fa.set_flow_style()  # whole component inline
    return cm


def _generic_component(data: Any) -> CommentedMap:
    """Fallback for an unknown component: keep the data, inline, quantized."""
    cm = CommentedMap()
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (list, tuple)):
                cm[k] = _flow_seq(list(v), quant=True)
            else:
                cm[k] = quantize(v)
    cm.fa.set_flow_style()
    return cm


def _entity(uuid: str, ent: dict[str, Any], schema: Schema) -> CommentedMap:
    cm = CommentedMap()
    cm["name"] = str(ent.get("name", uuid))

    comp_keys = [k for k in ent.keys() if k != "name"]
    ordered: list[str] = []
    if "Transform" in comp_keys:
        ordered.append("Transform")
    ordered += sorted(k for k in comp_keys if k != "Transform")

    for k in ordered:
        if schema.has(k):
            cm[k] = _component(k, ent.get(k) or {}, schema)
        else:
            cm[k] = _generic_component(ent.get(k) or {})
    return cm  # entity itself stays block style


def _natkey(s: str) -> list[Any]:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(s))]


def canonicalize(data: dict[str, Any], schema: Schema) -> CommentedMap:
    """Rebuild ``data`` into a canonical, byte-stable ruamel structure."""
    root = CommentedMap()
    root["version"] = int(data.get("version", schema.version))

    scenes_out = CommentedMap()
    scenes_src = data.get("scenes") or {}
    for sname in sorted(scenes_src.keys(), key=_natkey):
        scene = scenes_src.get(sname) or {}
        ents_src = scene.get("entities") or {}
        ents_out = CommentedMap()
        for uuid in sorted(ents_src.keys()):
            ents_out[uuid] = _entity(uuid, ents_src.get(uuid) or {}, schema)
        body = CommentedMap()
        body["entities"] = ents_out
        scenes_out[sname] = body

    root["scenes"] = scenes_out
    return root


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #
def _yaml() -> YAML:
    y = YAML()  # round-trip
    y.default_flow_style = False
    y.width = 1_000_000  # never wrap our inline flow leaves
    y.indent(mapping=2, sequence=2, offset=0)
    y.allow_unicode = True
    return y


def loads(text: str) -> dict[str, Any]:
    data = _yaml().load(text)
    return data if data is not None else {}


def load_file(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return loads(f.read())


def dumps(node: Any) -> str:
    stream = io.StringIO()
    _yaml().dump(node, stream)
    return stream.getvalue()


def canonical_yaml(data: dict[str, Any], schema: Schema) -> str:
    """Full pipeline: raw data dict -> canonical YAML string."""
    return dumps(canonicalize(data, schema))
