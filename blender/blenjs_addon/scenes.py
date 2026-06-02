"""JSON scenes <-> Blender Scene datablocks (spec §6.1, §6.5, §6.6, §6.8).

Import: load JSON, create one Blender Scene per game scene (the native scene
dropdown becomes the switcher), create an object per entity, stamp UUIDs, fill
component PropertyGroups, and resolve entity-ref pointers in a second pass.

Export: walk managed scenes/objects, read the native transform + active
components into a plain data dict, and hand it to ``io_json.canonical_json``.
"""

import os

import bmesh
import bpy

from . import io_json, schema, transform
from .uuids import ensure_uuid

UNIT_CUBE = "BLENJS_UnitCube"


def _unit_cube_mesh():
    me = bpy.data.meshes.get(UNIT_CUBE)
    if me is not None:
        return me
    me = bpy.data.meshes.new(UNIT_CUBE)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)  # edge length 1 => full extents == object scale
    bm.to_mesh(me)
    bm.free()
    return me


def _ref_fields(component: dict):
    """(single_ref_fields, array_ref_fields) for a component."""
    singles, arrays = [], []
    for f in component.get("fields", []):
        if f.get("type") == "entityRef":
            singles.append(f["name"])
        elif f.get("type") == "array" and f.get("itemType") == "entityRef":
            arrays.append(f["name"])
    return singles, arrays


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #
def _create_object(uuid: str, ent: dict, scene, sch: "io_json.Schema"):
    name = ent.get("name", uuid)
    obj = bpy.data.objects.new(name, _unit_cube_mesh() if "Collider" in ent else None)
    if obj.data is None:  # empty
        obj.empty_display_type = "PLAIN_AXES"
        obj.empty_display_size = 0.4
    scene.collection.objects.link(obj)
    obj["blenjs_uuid"] = uuid  # ID-property — the one namespace ensure_uuid reads (see uuids.py)

    # Native transform — convert the Y-up game frame into Blender's Z-up frame so
    # the level stands upright in the viewport (see transform.py).
    t = ent.get("Transform") or {}
    pos, rot, scale = transform.game_to_blender(t.get("pos"), t.get("rot"), t.get("scale"))
    obj.location = tuple(pos)
    obj.rotation_euler = tuple(rot)
    obj.scale = tuple(scale)

    # Scalar component fields (refs handled in pass 2).
    for comp_name, comp_data in ent.items():
        if comp_name in ("name", "Transform") or not sch.has(comp_name):
            continue
        setattr(obj, schema.component_active_name(comp_name), True)
        pg = getattr(obj, schema.component_pg_name(comp_name))
        _apply_scalars(pg, sch.components[comp_name], comp_data or {})
    return obj


def _apply_scalars(pg, component: dict, data: dict):
    for f in component.get("fields", []):
        name = f["name"]
        if name not in data:
            continue
        t = f["type"]
        if t == "entityRef" or (t == "array" and f.get("itemType") == "entityRef"):
            continue  # pass 2
        value = data[name]
        try:
            if t in ("vec2", "vec3", "vec4"):
                setattr(pg, name, tuple(value))
            elif t == "int":
                setattr(pg, name, int(value))
            elif t == "number":
                setattr(pg, name, float(value))
            elif t == "bool":
                setattr(pg, name, bool(value))
            else:  # enum / string
                setattr(pg, name, value)
        except (TypeError, ValueError) as e:
            print(f"[blenjs] could not set {component['name']}.{name} = {value!r}: {e}")


def _apply_refs(obj, ent: dict, uuid_to_obj: dict, sch: "io_json.Schema"):
    for comp_name, comp_data in ent.items():
        if comp_name in ("name", "Transform") or not sch.has(comp_name):
            continue
        comp = sch.components[comp_name]
        singles, arrays = _ref_fields(comp)
        if not singles and not arrays:
            continue
        pg = getattr(obj, schema.component_pg_name(comp_name))
        data = comp_data or {}
        for field in singles:
            target = uuid_to_obj.get(data.get(field))
            setattr(pg, field, target)
        for field in arrays:
            coll = getattr(pg, field)
            coll.clear()
            for ref_uuid in data.get(field, []) or []:
                item = coll.add()
                item.target = uuid_to_obj.get(ref_uuid)


def _clear_managed(scene):
    for obj in list(scene.collection.all_objects):
        if obj.get("blenjs_uuid"):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            # remove orphan mesh (cubes are shared via UNIT_CUBE so keep that one)
            if data is not None and data.name != UNIT_CUBE and data.users == 0:
                bpy.data.meshes.remove(data)


def import_game(filepath: str, context) -> str:
    sch = schema.get_schema()
    if sch is None:
        raise RuntimeError("BlenJS schema not loaded — set the schema path in add-on preferences.")

    data = io_json.load_file(filepath)
    wm = getattr(context, "window_manager", None)
    if wm is not None:  # absent under --background; harmless to skip the Cmd/Ctrl+S stash
        wm.blenjs_filepath = os.path.abspath(filepath)

    scenes_data = data.get("scenes") or {}
    first_scene = None
    for sname, sbody in scenes_data.items():
        sc = bpy.data.scenes.get(sname)
        if sc is None:
            sc = bpy.data.scenes.new(sname)
        sc.blenjs_managed = True
        _clear_managed(sc)

        ents = (sbody or {}).get("entities") or {}
        uuid_to_obj = {}
        for uuid, ent in ents.items():
            uuid_to_obj[uuid] = _create_object(uuid, ent or {}, sc, sch)
        for uuid, ent in ents.items():
            _apply_refs(uuid_to_obj[uuid], ent or {}, uuid_to_obj, sch)

        if first_scene is None:
            first_scene = sc

    win = getattr(context, "window", None)
    if first_scene is not None and win is not None:  # no window under --background
        win.scene = first_scene
    return filepath


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def _read_component(obj, component: dict) -> dict:
    pg = getattr(obj, schema.component_pg_name(component["name"]))
    out = {}
    for f in component.get("fields", []):
        name = f["name"]
        t = f["type"]
        if t in ("vec2", "vec3", "vec4"):
            out[name] = list(getattr(pg, name))
        elif t == "int":
            out[name] = int(getattr(pg, name))
        elif t == "number":
            out[name] = float(getattr(pg, name))
        elif t == "bool":
            out[name] = bool(getattr(pg, name))
        elif t == "entityRef":
            target = getattr(pg, name)
            out[name] = ensure_uuid(target) if target else ""
        elif t == "array" and f.get("itemType") == "entityRef":
            out[name] = [ensure_uuid(it.target) for it in getattr(pg, name) if it.target]
        else:  # enum / string
            out[name] = getattr(pg, name)
    return out


def build_data(sch: "io_json.Schema") -> dict:
    scenes_out = {}
    for sc in bpy.data.scenes:
        if not getattr(sc, "blenjs_managed", False):
            continue
        ents = {}
        for obj in sc.collection.all_objects:
            uuid = ensure_uuid(obj)
            pos, rot, scale = transform.blender_to_game(
                list(obj.location), list(obj.rotation_euler), list(obj.scale)
            )
            ent = {
                "name": obj.name,
                "Transform": {"pos": pos, "rot": rot, "scale": scale},
            }
            for comp in sch.components.values():
                cname = comp["name"]
                if cname == schema.NATIVE_TRANSFORM:
                    continue
                if getattr(obj, schema.component_active_name(cname), False):
                    ent[cname] = _read_component(obj, comp)
            ents[uuid] = ent
        scenes_out[sc.name] = {"entities": ents}
    return {"version": sch.version, "scenes": scenes_out}


def export_to_path(filepath: str) -> str:
    sch = schema.get_schema()
    if sch is None:
        raise RuntimeError("BlenJS schema not loaded — set the schema path in add-on preferences.")
    text = io_json.canonical_json(build_data(sch), sch)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    return filepath
