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

from . import io_yaml

_ADDON = __package__.partition(".")[0]

# Component handled by the native object transform rather than a PropertyGroup.
NATIVE_TRANSFORM = "Transform"

SAFE_VEC_SUBTYPES = {"XYZ", "TRANSLATION", "COLOR", "DIRECTION", "VELOCITY", "EULER", "QUATERNION", "NONE"}

# Module state, populated on register.
_schema: "io_yaml.Schema | None" = None
_component_pgs: "dict[str, type]" = {}
_registered_classes: "list[type]" = []
_object_attrs: "list[str]" = []


# --------------------------------------------------------------------------- #
# Locating the schema file
# --------------------------------------------------------------------------- #
def find_schema_path() -> "str | None":
    # 1) addon preference
    try:
        prefs = bpy.context.preferences.addons[_ADDON].preferences
        p = bpy.path.abspath(prefs.schema_path) if prefs.schema_path else ""
        if p and os.path.isfile(p):
            return p
    except (KeyError, AttributeError):
        pass
    # 2) environment override
    env = os.environ.get("BLENJS_SCHEMA")
    if env and os.path.isfile(env):
        return env
    here = os.path.dirname(__file__)
    # 3) bundled copy next to the add-on (zip distribution)
    local = os.path.join(here, "components.schema.json")
    if os.path.isfile(local):
        return local
    # 4) repo-relative (dev: add-on loaded straight from the repo)
    repo = os.path.abspath(os.path.join(here, "..", "..", "generated", "components.schema.json"))
    if os.path.isfile(repo):
        return repo
    return None


def get_schema() -> "io_yaml.Schema | None":
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
    global _schema, _component_pgs, _registered_classes, _object_attrs
    _component_pgs = {}
    _registered_classes = []
    _object_attrs = []

    path = find_schema_path()
    if not path:
        print("[blenjs] components.schema.json not found. Set the path in add-on preferences.")
        _schema = None
        return

    _schema = io_yaml.Schema.load(path)
    print(f"[blenjs] loaded schema v{_schema.version} from {path} ({len(_schema.components)} components)")

    # The array-element PG must be registered before any component PG references it.
    bpy.utils.register_class(BLENJS_PG_ObjectRef)
    _registered_classes.append(BLENJS_PG_ObjectRef)

    # Identity (``blenjs_uuid``) is a plain ID-property, NOT a registered RNA
    # StringProperty — see uuids.py. Registering it here would create a second
    # storage namespace (``obj.blenjs_uuid``) invisible to ``obj.get()``, breaking
    # UUID round-trip. It is stamped lazily via ``ensure_uuid`` (``obj["blenjs_uuid"]``).

    for component in behavior_or_data_components():
        name = component["name"]
        pg = _build_property_group(component)
        bpy.utils.register_class(pg)
        _registered_classes.append(pg)
        _component_pgs[name] = pg

        slot = component_pg_name(name)
        setattr(bpy.types.Object, slot, PointerProperty(type=pg))
        _object_attrs.append(slot)

        active = component_active_name(name)
        setattr(bpy.types.Object, active, BoolProperty(name=f"Has {name}", default=False))
        _object_attrs.append(active)


def unregister() -> None:
    global _schema
    for attr in reversed(_object_attrs):
        if hasattr(bpy.types.Object, attr):
            delattr(bpy.types.Object, attr)
    _object_attrs.clear()

    for cls in reversed(_registered_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    _registered_classes.clear()
    _component_pgs.clear()
    _schema = None
