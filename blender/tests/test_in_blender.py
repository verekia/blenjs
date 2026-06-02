#!/usr/bin/env python3
"""Authoritative in-Blender acceptance test (headless).

Runs the REAL add-on code against the REAL ``bpy`` inside Blender, proving the
data path that the fake-bpy test (``test_blender_roundtrip.py``) can only
approximate:

  1. load game.yaml -> Blender datablocks -> save  ==  zero diff
  2. entity-refs (``Patrol.waypoints``) round-trip with no phantom UUIDs
     (the regression: a UUID stored via ``obj.blenjs_uuid =`` is invisible to
     ``obj.get("blenjs_uuid")``, so ``ensure_uuid`` minted a fresh id per call
     and refs pointed at entities that never existed)
  3. re-import is idempotent — managed objects are replaced, not duplicated

Run::

    # ruamel.yaml must be importable by Blender's bundled python. Install it into
    # Blender, or point BLENJS_PYLIBS at a dir that contains it:
    BLENJS_PYLIBS=/path/to/libs \\
      blender --background --factory-startup \\
        --python blender/tests/test_in_blender.py

Prints ``BLENJS_INBLENDER_RESULT: PASS|FAIL`` and exits non-zero on failure.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

# Let ruamel (and any other dep) load from a writable dir when it is not installed
# into Blender's read-only bundled python.
for _extra in filter(None, os.environ.get("BLENJS_PYLIBS", "").split(os.pathsep)):
    sys.path.insert(0, _extra)
sys.path.insert(0, os.path.join(ROOT, "blender"))  # the blenjs_addon package

import bpy  # noqa: E402  — the real Blender module
from bpy.props import BoolProperty, StringProperty  # noqa: E402

import blenjs_addon.io_yaml as io_yaml  # noqa: E402
import blenjs_addon.scenes as scenes  # noqa: E402
import blenjs_addon.schema as schema  # noqa: E402

GAME_PATH = os.path.join(ROOT, "game.yaml")


def _diff(a: str, b: str) -> str:
    import difflib

    return "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), "expected", "actual"))


def _register() -> None:
    """The minimal slice of __init__.register() the data path needs."""
    schema.register()
    if not hasattr(bpy.types.Scene, "blenjs_managed"):
        bpy.types.Scene.blenjs_managed = BoolProperty(default=False)
    if not hasattr(bpy.types.WindowManager, "blenjs_filepath"):
        bpy.types.WindowManager.blenjs_filepath = StringProperty(default="", subtype="FILE_PATH")


def _entity_counts(sch) -> dict:
    data = scenes.build_data(sch)
    return {s: len(b["entities"]) for s, b in data["scenes"].items()}


def main() -> int:
    _register()
    sch = schema.get_schema()
    if sch is None:
        print("FAIL: schema did not load (set BLENJS_SCHEMA or run from the repo)")
        return 1

    with open(GAME_PATH, "r", encoding="utf-8") as f:
        original = f.read()

    failures = 0

    # 1) load -> datablocks -> save == zero diff
    scenes.import_game(GAME_PATH, bpy.context)
    rebuilt = io_yaml.canonical_yaml(scenes.build_data(sch), sch)
    if rebuilt == original:
        print("PASS: datablock round-trip is byte-stable (load -> datablocks -> save == zero diff)")
    else:
        failures += 1
        print("FAIL: datablock round-trip produced a diff:")
        print(_diff(original, rebuilt))

    # 2) entity-ref waypoints resolve to real entities (the bug under test)
    ents = scenes.build_data(sch)["scenes"]["level1"]["entities"]
    keys = set(ents)
    phantom = []
    n_refs = 0
    for ent in ents.values():
        patrol = ent.get("Patrol")
        if not patrol:
            continue
        for wp in patrol.get("waypoints", []):
            n_refs += 1
            if wp not in keys:
                phantom.append((ent.get("name"), wp))
    if n_refs >= 4 and not phantom:
        print(f"PASS: all {n_refs} Patrol.waypoints resolve to real entities (no phantom UUIDs)")
    else:
        failures += 1
        print(f"FAIL: waypoint refs broken (checked {n_refs}, phantom={phantom!r})")

    # 3) re-import is idempotent — managed objects replaced, not duplicated
    before = _entity_counts(sch)
    scenes.import_game(GAME_PATH, bpy.context)
    after = _entity_counts(sch)
    if before == after:
        print(f"PASS: re-import is idempotent (entity counts stable: {after})")
    else:
        failures += 1
        print(f"FAIL: re-import changed entity counts: {before} -> {after}")

    print()
    print("BLENJS_INBLENDER_RESULT: " + ("FAIL" if failures else "PASS"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
