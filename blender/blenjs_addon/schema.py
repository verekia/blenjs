"""Schema-driven dynamic PropertyGroups (spec §6.2, §6.3).

At register time we read ``components.schema.json`` and build one PropertyGroup
per component via ``type(...)``, mapping field types to ``bpy.props``. Components
are stacked on objects using the Blenvy-style pattern: a fixed
``PointerProperty`` slot per component type on ``bpy.types.Object`` plus a
per-component "active" boolean (the active-set). Panels/export only touch active
slots; inactive slots cost nothing.

``Transform`` is special-cased: it maps to the object's NATIVE transform
(location / rotation_euler / scale), so designers just move objects normally.
"""

import os

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from . import io_json

# Component handled by the native object transform rather than a PropertyGroup.
NATIVE_TRANSFORM = "Transform"

SAFE_VEC_SUBTYPES = {"XYZ", "TRANSLATION", "COLOR", "DIRECTION", "VELOCITY", "EULER", "QUATERNION", "NONE"}

# Module state. The schema-driven PropertyGroups are PER-PROJECT: built by apply_schema()
# when a .blen.json is loaded (the schema resolved relative to the project root), not at
# add-on enable. BLENJS_PG_ObjectRef is the one static class.
_schema: "io_json.Schema | None" = None
_component_pgs: "dict[str, type]" = {}
_dynamic_classes: "list[type]" = []
_object_attrs: "list[str]" = []


def get_schema() -> "io_json.Schema | None":
    return _schema


def ordered_components() -> list:
    if _schema is None:
        return []
    return list(_schema.components.values())


def behavior_or_data_components() -> list:
    """All components except the native Transform."""
    return [c for c in ordered_components() if c["name"] != NATIVE_TRANSFORM]


# --------------------------------------------------------------------------- #
# Field -> bpy.props mapping
# --------------------------------------------------------------------------- #
class BLENJS_PG_ObjectRef(bpy.types.PropertyGroup):
    """One element of an entity-ref array field (homogeneous -> CollectionProperty)."""

    target: PointerProperty(type=bpy.types.Object, name="Target")


def _prop_for_field(field: dict):
    t = field.get("type")
    name = field.get("name", "")
    tip = field.get("tooltip", "") or ""
    default = field.get("default")

    if t == "number":
        kw = dict(name=name, description=tip)
        if isinstance(default, (int, float)):
            kw["default"] = float(default)
        if isinstance(field.get("min"), (int, float)):
            kw["min"] = float(field["min"])
        if isinstance(field.get("max"), (int, float)):
            kw["max"] = float(field["max"])
        if isinstance(field.get("step"), (int, float)):
            kw["step"] = max(1, int(round(float(field["step"]) * 100)))  # Blender step is in 1/100 units
        return FloatProperty(**kw)

    if t == "int":
        kw = dict(name=name, description=tip)
        if isinstance(default, (int, float)):
            kw["default"] = int(default)
        if isinstance(field.get("min"), (int, float)):
            kw["min"] = int(field["min"])
        if isinstance(field.get("max"), (int, float)):
            kw["max"] = int(field["max"])
        return IntProperty(**kw)

    if t == "bool":
        return BoolProperty(name=name, description=tip, default=bool(default))

    if t == "enum":
        vals = field.get("enumValues") or []
        items = [(v, v[:1].upper() + v[1:], "") for v in vals]
        kw = dict(name=name, description=tip, items=items)
        if isinstance(default, str) and default in vals:
            kw["default"] = default
        return EnumProperty(**kw)

    if t in ("vec2", "vec3", "vec4"):
        n = int(t[-1])
        sub = field.get("subtype", "NONE")
        if sub not in SAFE_VEC_SUBTYPES:
            sub = "NONE"
        if isinstance(default, (list, tuple)) and len(default) == n:
            d = tuple(float(x) for x in default)
        else:
            d = tuple([0.0] * n)
        return FloatVectorProperty(name=name, description=tip, size=n, subtype=sub, default=d)

    if t == "entityRef":
        return PointerProperty(type=bpy.types.Object, name=name, description=tip)

    if t == "array":
        if field.get("itemType") == "entityRef":
            return CollectionProperty(type=BLENJS_PG_ObjectRef, name=name, description=tip)
        return StringProperty(name=name, description=tip, default="")  # generic fallback

    # string / unknown
    return StringProperty(name=name, description=tip, default=str(default) if isinstance(default, str) else "")


def _build_property_group(component: dict) -> type:
    annotations: dict = {}
    for field in component.get("fields", []):
        annotations[field["name"]] = _prop_for_field(field)
        # UIList index companion for entity-ref arrays
        if field.get("type") == "array" and field.get("itemType") == "entityRef":
            annotations[f"{field['name']}_index"] = IntProperty(default=0)
    cls_name = f"BLENJS_PG_{component['name']}"
    return type(cls_name, (bpy.types.PropertyGroup,), {"__annotations__": annotations})


def component_pg_name(component_name: str) -> str:
    return f"blenjs_{component_name}"


def component_active_name(component_name: str) -> str:
    return f"blenjs_has_{component_name}"


# --------------------------------------------------------------------------- #
# Register / unregister
# --------------------------------------------------------------------------- #
def register() -> None:
    """Add-on enable: register only the static part. The schema-driven PropertyGroups are
    built per project by ``apply_schema`` when a .blen.json is loaded."""
    global _schema, _component_pgs, _dynamic_classes, _object_attrs
    _schema = None
    _component_pgs = {}
    _dynamic_classes = []
    _object_attrs = []
    # The entity-ref array element PG is static; component PGs reference it.
    bpy.utils.register_class(BLENJS_PG_ObjectRef)


def clear_dynamic() -> None:
    """Tear down the per-project schema-driven PGs + per-object slots (idempotent)."""
    global _schema, _component_pgs, _dynamic_classes, _object_attrs
    for attr in reversed(_object_attrs):
        if hasattr(bpy.types.Object, attr):
            delattr(bpy.types.Object, attr)
    _object_attrs = []
    for cls in reversed(_dynamic_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    _dynamic_classes = []
    _component_pgs = {}
    _schema = None


def apply_schema(path: str) -> "io_json.Schema | None":
    """(Re)build the PropertyGroups from a project's ``components.schema.json`` (``path``
    resolved via project.py). Called when a .blen.json is loaded; safe to call repeatedly — the
    previous project's PGs are torn down first, so re-loading after ``bun run codegen`` picks up
    the new schema. Returns the loaded Schema, or None if the file is missing.

    Identity (``blenjs_uuid``) is a plain ID-property, not a registered RNA prop (see uuids.py),
    so it survives this register/unregister churn."""
    clear_dynamic()
    if not path or not os.path.isfile(path):
        print(f"[blenjs] components.schema.json not found at {path} — run `bun run codegen`.")
        return None

    global _schema
    _schema = io_json.Schema.load(path)
    print(f"[blenjs] loaded schema v{_schema.version} from {path} ({len(_schema.components)} components)")

    for component in behavior_or_data_components():
        name = component["name"]
        pg = _build_property_group(component)
        bpy.utils.register_class(pg)
        _dynamic_classes.append(pg)
        _component_pgs[name] = pg

        slot = component_pg_name(name)
        setattr(bpy.types.Object, slot, PointerProperty(type=pg))
        _object_attrs.append(slot)

        active = component_active_name(name)
        setattr(bpy.types.Object, active, BoolProperty(name=f"Has {name}", default=False))
        _object_attrs.append(active)
    return _schema


def unregister() -> None:
    clear_dynamic()
    try:
        bpy.utils.unregister_class(BLENJS_PG_ObjectRef)
    except RuntimeError:
        pass
