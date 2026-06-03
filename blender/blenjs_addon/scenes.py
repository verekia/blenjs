"""JSON scenes <-> Blender Scene datablocks (spec §6.1, §6.5, §6.6, §6.8).

Import: load JSON, create one Blender Scene per game scene (the native scene
dropdown becomes the switcher), create an object per entity, stamp UUIDs, fill
component PropertyGroups, and resolve entity-ref pointers in a second pass.

Prefab instances (entities with a ``prefab`` key) and entities carrying a ``Model``
component are visualized with their REAL geometry by LIBRARY-LINKING the editable
source ``<root>/prefabs/<src>.blend`` (Blender's "library" feature) and showing it as a
COLLECTION INSTANCE: the geometry lives in the external .blend and is only *referenced*,
never copied into the scene. One linked holder collection is created per asset and shared
by every instance; the entity is an Empty that instances it. Because the source is native
Z-up, no rotation correction is needed (unlike the old glTF import path). ``Model.src`` is
a bare name (``"coin"`` → ``prefabs/coin.blend``); the built ``.glb`` is only the web
runtime's artifact and is never referenced here. Prefab data is resolved (prefab defaults
+ per-instance overrides) so the inspector shows real values; on export it is diffed back
to a sparse override set. Linking is best-effort — if the .blend (or the linking API) is
unavailable (headless tests, fresh checkout) instances fall back to a placeholder while
the data path (UUIDs, components, refs) stays intact.

Export: walk managed scenes/objects, read the native transform + active components
into a plain data dict, and hand it to ``io_json.canonical_json``.
"""

import os

import bmesh
import bpy

from . import io_json, prefabs, project, schema, transform
from .uuids import ensure_uuid

UNIT_CUBE = "BLENJS_UnitCube"
HOLDER_PREFIX = "BLENJS_SRC_"  # local collections that hold linked source objects for instancing

# Linked holder collections (keyed by asset src) + the resolved prefab-sources directory.
# Both reset per import_game so a rebuilt .blend — and the right repo — are picked up each load.
_holders: dict = {}
_prefabs_dir: "str | None" = None
# True while import_game is populating scenes, so the Model.src `update=` callback (live model
# swap) stays quiet for the programmatic writes in _apply_scalars (see on_model_src_update).
_loading: bool = False


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


def _model_blend_path(src: str) -> str:
    """Absolute path to the editable source ``<prefabs>/<src>.blend`` for a bare model name
    (``Model.src`` = ``"coin"`` -> ``.../prefabs/coin.blend``). The built ``.glb`` is never
    referenced here — it is only the web runtime's artifact."""
    return os.path.abspath(os.path.join(_prefabs_dir or "", src + ".blend"))


def _link_holder(blend_path: str, asset: str):
    """LINK every object from ``blend_path`` (read-only library data) into a fresh LOCAL
    collection ``BLENJS_SRC_<asset>`` and return it. The holder is never added to a view layer,
    so the source shows up ONLY through collection instances of it — its geometry is referenced,
    not copied into the scene. Linking an object auto-pulls its mesh, material and (live)
    modifiers, and the source is native Z-up, so no rotation correction is needed. Returns
    ``None`` if nothing linked."""
    name = HOLDER_PREFIX + asset
    holder = bpy.data.collections.get(name)
    if holder is not None:
        return holder
    with bpy.data.libraries.load(blend_path, link=True) as (data_from, data_to):
        data_to.objects = list(data_from.objects)  # the source .blend holds exactly one object today
    holder = bpy.data.collections.new(name)
    for obj in data_to.objects:
        if obj is not None:  # libraries.load yields None for any name it could not resolve
            holder.objects.link(obj)
    if not holder.objects:
        bpy.data.collections.remove(holder)
        return None
    return holder


def _holder_for(src: str):
    """Linked holder collection for a model ``src`` (cached for this import; many instances share
    it). Best-effort: returns ``None`` — so the caller falls back to a placeholder — if the linking
    API is unavailable (fake bpy / headless) or the .blend is missing."""
    if src in _holders:
        return _holders[src]
    holder = None
    blend_path = _model_blend_path(src)
    try:
        if hasattr(bpy.data, "libraries") and os.path.isfile(blend_path):
            holder = _link_holder(blend_path, src)
    except Exception as e:  # noqa: BLE001 — visualization is best-effort
        print(f"[blenjs] could not link model '{src}' from {blend_path}: {e}")
        holder = None
    _holders[src] = holder
    return holder


def _purge_holders_and_libs() -> None:
    """Drop every linked holder collection + its linked datablocks + the source libraries, so a
    re-import re-links fresh (a rebuilt .blend is picked up) with no ``.001`` duplicates piling up.
    Defensive: a no-op under the fake bpy (no collections/libraries/orphans_purge)."""
    colls = getattr(bpy.data, "collections", None)
    if colls is not None:
        for c in list(colls):
            if c.name.startswith(HOLDER_PREFIX):
                for obj in list(c.objects):
                    bpy.data.objects.remove(obj, do_unlink=True)
                colls.remove(c)
    purge = getattr(bpy.data, "orphans_purge", None)
    if callable(purge):
        try:
            purge(do_local_ids=False, do_linked_ids=True, do_recursive=True)
        except Exception as e:  # noqa: BLE001
            print(f"[blenjs] orphans_purge skipped: {e}")
    libs = getattr(bpy.data, "libraries", None)
    if libs is not None:
        # A library's user count never returns to 0 once its data is gone, so removing only when
        # users==0 would leak; remove unconditionally (nothing references it by now).
        for lib in list(libs):
            try:
                libs.remove(lib)
            except Exception as e:  # noqa: BLE001
                print(f"[blenjs] could not remove library {getattr(lib, 'filepath', '?')}: {e}")


def _apply_holder(obj, holder) -> None:
    """Turn ``obj`` into a collection instance of the linked ``holder`` (the model's geometry,
    referenced from its .blend). The instanced geometry is the visual, so the empty's own axes
    cross is hidden."""
    obj.instance_type = "COLLECTION"
    obj.instance_collection = holder
    obj.empty_display_size = 0.0


def _clear_holder(obj) -> None:
    """Drop ``obj``'s collection instance and restore the empty marker (model missing/cleared)."""
    obj.instance_collection = None
    obj.instance_type = "NONE"
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.4


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
def _model_src(ent: dict) -> "str | None":
    model = ent.get("Model")
    if isinstance(model, dict):
        src = model.get("src")
        if isinstance(src, str) and src:
            return src
    return None


def _create_object(uuid: str, ent: dict, scene, sch: "io_json.Schema", prefab_name: "str | None"):
    """``ent`` is the RESOLVED entity body (prefab defaults + overrides already merged);
    ``prefab_name`` is set for prefab instances so export can re-sparsify."""
    name = ent.get("name", uuid)

    # Geometry: a Model asset (prefab or single-use) renders as a linked-collection INSTANCE
    # (the .blend is referenced, not copied) > a Collider's unit cube > an empty marker.
    src = _model_src(ent)
    holder = _holder_for(src) if src else None
    mesh = _unit_cube_mesh() if holder is None and "Collider" in ent else None

    obj = bpy.data.objects.new(name, mesh)
    if holder is not None:  # instance the linked source — geometry stays in the .blend
        _apply_holder(obj, holder)
    elif obj.data is None:  # empty (marker / model unavailable)
        obj.empty_display_type = "PLAIN_AXES"
        obj.empty_display_size = 0.4
    scene.collection.objects.link(obj)
    obj["blenjs_uuid"] = uuid  # ID-property — the one namespace ensure_uuid reads (see uuids.py)
    if prefab_name:
        obj["blenjs_prefab"] = prefab_name  # remembered so export re-sparsifies overrides

    # Native transform — convert the game frame into Blender's frame (see transform.py).
    t = ent.get("Transform") or {}
    pos, rot, scale = transform.game_to_blender(
        t.get("pos") or [0, 0, 0], t.get("rot") or [0, 0, 0], t.get("scale") or [1, 1, 1]
    )
    obj.location = tuple(pos)
    obj.rotation_euler = tuple(rot)
    obj.scale = tuple(scale)

    # Scalar component fields (refs handled in pass 2).
    for comp_name, comp_data in ent.items():
        if comp_name in ("name", "Transform", "prefab") or not sch.has(comp_name):
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
        if comp_name in ("name", "Transform", "prefab") or not sch.has(comp_name):
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


def _resolved_body(uuid: str, ent: dict) -> "tuple[dict, str | None]":
    """Return (display body, prefab_name). For a prefab instance the body is the prefab's
    components merged with the instance overrides; otherwise the entity is returned as-is."""
    prefab_name = ent.get("prefab") if isinstance(ent.get("prefab"), str) and ent.get("prefab") else None
    if prefab_name:
        body = {"name": ent.get("name", uuid)}
        body.update(prefabs.resolve_components(prefab_name, ent))
        return body, prefab_name
    return ent, None


def _clear_managed(scene):
    for obj in list(scene.collection.all_objects):
        if obj.get("blenjs_uuid"):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            # remove orphan mesh (the shared unit cube is kept). Model entities are instance
            # empties (no mesh); linked source geometry is purged via _purge_holders_and_libs.
            if data is not None and data.name != UNIT_CUBE and data.users == 0:
                bpy.data.meshes.remove(data)


def import_game(filepath: str, context) -> str:
    # A BlenJS project root is the folder containing the .blen.json; the schema, prefab
    # manifest, and model sources (prefabs/*.blend) are all resolved from there (see project.py).
    root = project.root_of(filepath)
    sch = schema.apply_schema(project.schema_path(root))  # (re)builds PGs for THIS project
    if sch is None:
        raise RuntimeError(
            f"components.schema.json not found under {root} "
            f"(expected generated/components.schema.json) — run `bun run codegen`."
        )

    data = io_json.load_file(filepath)
    prefabs.load(project.prefabs_path(root))
    global _prefabs_dir, _loading
    _prefabs_dir = project.prefabs_dir(root)
    _purge_holders_and_libs()  # drop the previous import's linked libraries/holders first
    _holders.clear()  # re-link fresh each load (picks up a rebuilt .blend)

    wm = getattr(context, "window_manager", None)
    if wm is not None:  # absent under --background; harmless to skip the Cmd/Ctrl+S stash
        wm.blenjs_filepath = os.path.abspath(filepath)

    scenes_data = data.get("scenes") or {}
    first_scene = None
    _loading = True  # quiet the Model.src live-swap callback while fields are set programmatically
    try:
        for sname, sbody in scenes_data.items():
            sc = bpy.data.scenes.get(sname)
            if sc is None:
                sc = bpy.data.scenes.new(sname)
            sc.blenjs_managed = True
            _clear_managed(sc)

            ents = (sbody or {}).get("entities") or {}
            resolved = {uuid: _resolved_body(uuid, ent or {}) for uuid, ent in ents.items()}
            uuid_to_obj = {}
            for uuid, (body, prefab_name) in resolved.items():
                uuid_to_obj[uuid] = _create_object(uuid, body, sc, sch, prefab_name)
            for uuid, (body, _prefab_name) in resolved.items():
                _apply_refs(uuid_to_obj[uuid], body, uuid_to_obj, sch)

            if first_scene is None:
                first_scene = sc
    finally:
        _loading = False

    linked = [s for s, h in _holders.items() if h is not None]
    missing = [s for s, h in _holders.items() if h is None]
    if missing:
        print(f"[blenjs] {len(linked)} model(s) linked; MISSING {missing} — no .blend in {_prefabs_dir}")
    elif linked:
        print(f"[blenjs] {len(linked)} model(s) linked from {_prefabs_dir}")

    win = getattr(context, "window", None)
    if first_scene is not None and win is not None:  # no window under --background
        win.scene = first_scene
    return filepath


def on_model_src_update(pg, context) -> None:
    """``update=`` callback for the ``Model.src`` field (wired in schema.py): re-link the new
    source and swap the entity's collection instance LIVE, so renaming the model in the inspector
    immediately changes the model in the viewport. A no-op during an import (``_loading``), when
    the field is set programmatically, and best-effort otherwise."""
    global _prefabs_dir
    if _loading:
        return
    obj = getattr(pg, "id_data", None)  # the Object that owns this Model PropertyGroup
    if not isinstance(obj, bpy.types.Object) or not obj.get("blenjs_uuid"):
        return
    wm = getattr(bpy.context, "window_manager", None)
    fp = getattr(wm, "blenjs_filepath", "") if wm is not None else ""
    if not fp:  # no project path known (never imported) — nothing to resolve sources against
        return
    try:
        _prefabs_dir = project.prefabs_dir(project.root_of(fp))
        src = pg.src
        holder = _holder_for(src) if src else None
        if holder is not None:
            _apply_holder(obj, holder)
        else:
            _clear_holder(obj)
    except Exception as e:  # noqa: BLE001 — live visualization is best-effort
        print(f"[blenjs] could not swap model to '{getattr(pg, 'src', '')}': {e}")


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


def _native_transform(obj) -> dict:
    pos, rot, scale = transform.blender_to_game(list(obj.location), list(obj.rotation_euler), list(obj.scale))
    return {"pos": pos, "rot": rot, "scale": scale}


def _build_plain_entity(obj, sch: "io_json.Schema") -> dict:
    ent = {"name": obj.name, "Transform": _native_transform(obj)}
    for comp in sch.components.values():
        cname = comp["name"]
        if cname == schema.NATIVE_TRANSFORM:
            continue
        if getattr(obj, schema.component_active_name(cname), False):
            ent[cname] = _read_component(obj, comp)
    return ent


def _prefab_field(comp: str, field: str, pcomps: dict, sch: "io_json.Schema"):
    """The prefab's effective value for ``comp.field``: its override if present, else the
    schema default (what the prefab inherits)."""
    cdata = pcomps.get(comp) or {}
    return cdata[field] if field in cdata else sch.default(comp, field)


def _same(field: dict, a, b) -> bool:
    """Canonical-equality of two values for a schema field (quantized, so float noise and
    1 vs 1.0 do not register as an override)."""
    return io_json._value_for_field(field, a) == io_json._value_for_field(field, b)


def _build_prefab_entity(obj, prefab_name: str, sch: "io_json.Schema") -> dict:
    """A prefab instance: emit ``prefab`` + only what differs from the prefab (Transform
    diffed field-by-field; each active component diffed field-by-field). Components/fields
    equal to the prefab are omitted (inherited at load)."""
    pcomps = (prefabs.definition(prefab_name) or {}).get("components") or {}
    ent = {"name": obj.name, "prefab": prefab_name}

    cur_t = _native_transform(obj)
    t_fields = (sch.components.get(schema.NATIVE_TRANSFORM) or {}).get("fields", [])
    t_diff = {
        f["name"]: cur_t[f["name"]]
        for f in t_fields
        if not _same(f, cur_t[f["name"]], _prefab_field(schema.NATIVE_TRANSFORM, f["name"], pcomps, sch))
    }
    if t_diff:
        ent["Transform"] = t_diff

    for comp in sch.components.values():
        cname = comp["name"]
        if cname == schema.NATIVE_TRANSFORM or not getattr(obj, schema.component_active_name(cname), False):
            continue
        cur = _read_component(obj, comp)
        if cname not in pcomps:
            ent[cname] = cur  # active but not in the prefab (instance-only) — keep it whole
            continue
        diff = {f["name"]: cur[f["name"]] for f in comp.get("fields", []) if not _same(f, cur[f["name"]], _prefab_field(cname, f["name"], pcomps, sch))}
        if diff:
            ent[cname] = diff
    return ent


def build_data(sch: "io_json.Schema") -> dict:
    scenes_out = {}
    for sc in bpy.data.scenes:
        if not getattr(sc, "blenjs_managed", False):
            continue
        ents = {}
        for obj in sc.collection.all_objects:
            uuid = ensure_uuid(obj)
            prefab_name = obj.get("blenjs_prefab")
            if prefab_name:
                ents[uuid] = _build_prefab_entity(obj, prefab_name, sch)
            else:
                ents[uuid] = _build_plain_entity(obj, sch)
        scenes_out[sc.name] = {"entities": ents}
    return {"version": sch.version, "scenes": scenes_out}


def export_to_path(filepath: str) -> str:
    sch = schema.get_schema()
    if sch is None:
        raise RuntimeError("No BlenJS project loaded — load a .blen.json first (drag it into the viewport).")
    text = io_json.canonical_json(build_data(sch), sch)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    return filepath
