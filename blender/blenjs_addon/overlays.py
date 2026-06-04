"""Viewport overlay that draws Collider volumes (box / sphere / capsule) as wireframes.

Toggle lives in the 3D viewport's **Overlays** popover (a sub-panel parented to
``VIEW3D_PT_overlay``), so it feels native — alongside Blender's own overlays. The shape
matches the runtime exactly: a box uses ``Transform.scale`` as full extents (oriented by the
object, so rotation shows), a sphere's radius is ``0.5·max(scale)``, and a capsule is a
``0.5·max(scale.x, scale.y)``-radius column of height ``scale.z`` along the object's local Z.

The ``gpu`` modules are imported lazily inside the draw callback so the add-on still registers
in headless Blender (``--background``), where there is no draw context. The segment generators
are pure (mathutils only) and are exercised by ``blender/tests/test_overlay_shapes.py``.
"""

import math

import bpy

from . import schema

# `mathutils` and `gpu` are imported lazily (inside the functions below) so this module — and
# therefore the add-on package — still imports under plain CPython (the fake-bpy round-trip test),
# where neither is available. They are only ever needed inside a real Blender draw/viewport.

_handle = None
COLOR = (0.25, 1.0, 0.45, 0.9)  # collider wire colour (RGBA)
_CIRCLE_SEGMENTS = 28


# --------------------------------------------------------------------------- #
# Shape -> world-space line segments (pure; no gpu)
# --------------------------------------------------------------------------- #
def collider_shape(obj) -> "str | None":
    """The active Collider's shape for ``obj`` (``box`` default), or ``None`` if the object
    has no active Collider / the schema PGs are not built (no project loaded)."""
    if not getattr(obj, schema.component_active_name("Collider"), False):
        return None
    pg = getattr(obj, schema.component_pg_name("Collider"), None)
    if pg is None:
        return None
    return getattr(pg, "shape", "box") or "box"


_BOX_EDGES = (
    (0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3),
    (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7),
)


def _box_segments(obj) -> list:
    from mathutils import Vector  # noqa: PLC0415 — lazy (see module header)

    mw = obj.matrix_world
    # A unit cube (±0.5) through matrix_world == the collider box (scale = full extents),
    # oriented by the object's rotation. Corner index bits are (x,y,z).
    corners = [mw @ Vector((x, y, z)) for x in (-0.5, 0.5) for y in (-0.5, 0.5) for z in (-0.5, 0.5)]
    return [(corners[a], corners[b]) for a, b in _BOX_EDGES]


def _ring(center, b1, b2, radius, n=_CIRCLE_SEGMENTS) -> list:
    """A closed circle of `radius` in the plane spanned by orthonormal `b1`,`b2`, around `center`."""
    segs = []
    prev = None
    for i in range(n + 1):
        a = 2.0 * math.pi * i / n
        p = center + (b1 * (math.cos(a) * radius)) + (b2 * (math.sin(a) * radius))
        if prev is not None:
            segs.append((prev, p))
        prev = p
    return segs


def _sphere_segments(obj) -> list:
    from mathutils import Vector  # noqa: PLC0415 — lazy (see module header)

    center = obj.matrix_world.translation
    s = obj.scale
    r = 0.5 * max(abs(s.x), abs(s.y), abs(s.z))
    x, y, z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
    return _ring(center, x, y, r) + _ring(center, x, z, r) + _ring(center, y, z, r)


def _capsule_segments(obj) -> list:
    from mathutils import Vector  # noqa: PLC0415 — lazy (see module header)

    q = obj.matrix_world.to_quaternion()
    axis = (q @ Vector((0, 0, 1))).normalized()
    s = obj.scale
    r = 0.5 * max(abs(s.x), abs(s.y))
    half_h = max(0.0, 0.5 * abs(s.z) - r)  # half-distance between the two cap centres
    center = obj.matrix_world.translation
    top, bot = center + axis * half_h, center - axis * half_h
    u = axis.cross(Vector((1, 0, 0)))
    if u.length < 1e-4:
        u = axis.cross(Vector((0, 1, 0)))
    u.normalize()
    v = axis.cross(u).normalized()

    segs = _ring(top, u, v, r) + _ring(bot, u, v, r)  # the two end rings
    for d in (u, v, -u, -v):  # 4 side lines
        segs.append((bot + d * r, top + d * r))
    for w in (u, v):  # a half-circle cap at each pole, in the (w, axis) plane
        for cap, sgn in ((top, 1.0), (bot, -1.0)):
            prev = None
            for i in range(_CIRCLE_SEGMENTS // 2 + 1):
                a = math.pi * i / (_CIRCLE_SEGMENTS // 2)
                p = cap + (w * (math.cos(a) * r)) + (axis * (sgn * math.sin(a) * r))
                if prev is not None:
                    segs.append((prev, p))
                prev = p
    return segs


def collider_segments(obj, shape: str) -> list:
    if shape == "sphere":
        return _sphere_segments(obj)
    if shape == "capsule":
        return _capsule_segments(obj)
    return _box_segments(obj)


# --------------------------------------------------------------------------- #
# Draw handler (GUI only — gpu imported lazily)
# --------------------------------------------------------------------------- #
def _draw() -> None:
    try:
        scene = bpy.context.scene
        if scene is None or not getattr(scene, "blenjs_show_colliders", False):
            return
        if not getattr(scene, "blenjs_managed", False):
            return  # only annotate BlenJS scenes

        coords = []
        for obj in scene.collection.all_objects:
            if not obj.get("blenjs_uuid"):
                continue
            shape = collider_shape(obj)
            if shape is None:
                continue
            for a, b in collider_segments(obj, shape):
                coords.append(a)
                coords.append(b)
        if not coords:
            return

        import gpu  # noqa: PLC0415 — lazy: avoids needing a GPU context at add-on register
        from gpu_extras.batch import batch_for_shader  # noqa: PLC0415

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "LINES", {"pos": [tuple(c) for c in coords]})
        gpu.state.blend_set("ALPHA")
        gpu.state.line_width_set(1.5)
        shader.bind()
        shader.uniform_float("color", COLOR)
        batch.draw(shader)
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set("NONE")
    except Exception as e:  # noqa: BLE001 — never let a draw error spam the console / break the view
        print(f"[blenjs] collider overlay draw error: {e}")


# --------------------------------------------------------------------------- #
# Toggle UI — a sub-panel inside the viewport Overlays popover
# --------------------------------------------------------------------------- #
class BLENJS_PT_overlay_colliders(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"
    bl_parent_id = "VIEW3D_PT_overlay"
    bl_label = "BlenJS"

    def draw(self, context):
        self.layout.prop(context.scene, "blenjs_show_colliders", text="Colliders")


def register() -> None:
    global _handle
    bpy.types.Scene.blenjs_show_colliders = bpy.props.BoolProperty(
        name="Colliders",
        description="Draw BlenJS Collider volumes (box / sphere / capsule) in the viewport",
        default=True,
    )
    bpy.utils.register_class(BLENJS_PT_overlay_colliders)
    if _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")


def unregister() -> None:
    global _handle
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, "WINDOW")
        _handle = None
    try:
        bpy.utils.unregister_class(BLENJS_PT_overlay_colliders)
    except RuntimeError:
        pass
    if hasattr(bpy.types.Scene, "blenjs_show_colliders"):
        del bpy.types.Scene.blenjs_show_colliders
