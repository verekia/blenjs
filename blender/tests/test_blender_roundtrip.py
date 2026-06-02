#!/usr/bin/env python3
"""Blender datablock round-trip — the in-Blender acceptance test, headless.

Drives the REAL add-on code (schema.register, scenes.import_game,
scenes.build_data) against a fake bpy, proving:

    load game.json -> Blender datablocks -> save  ==  zero diff

This complements test_roundtrip.py (which tests only the JSON canonicalizer): it
also exercises the native-transform mapping, the dynamic PropertyGroup slots, the
active-set, and UUID entity-ref resolution. The authoritative test is still
running the add-on inside Blender, but this catches data-mapping regressions in CI.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)  # fake_bpy
sys.path.insert(0, os.path.join(ROOT, "blender"))  # blenjs_addon package

import fake_bpy  # noqa: E402

bpy = fake_bpy.install()

import blenjs_addon.io_json as io_json  # noqa: E402
import blenjs_addon.scenes as scenes  # noqa: E402
import blenjs_addon.schema as schema  # noqa: E402

GAME_PATH = os.path.join(ROOT, "game.json")

OK = "\033[32m"
FAIL = "\033[31m"
END = "\033[0m"


def _diff(a: str, b: str) -> str:
    import difflib

    return "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), "expected", "actual"))


def main() -> int:
    schema.register()
    sch = schema.get_schema()
    if sch is None:
        print(f"{FAIL}FAIL{END} schema did not load")
        return 1

    with open(GAME_PATH, "r", encoding="utf-8") as f:
        original = f.read()

    # Import the JSON into fake datablocks, then export straight back.
    scenes.import_game(GAME_PATH, bpy.context)
    rebuilt = io_json.canonical_json(scenes.build_data(sch), sch)

    failures = 0
    if rebuilt == original:
        print(f"{OK}PASS{END} datablock round-trip is byte-stable (load -> datablocks -> save == zero diff)")
    else:
        failures += 1
        print(f"{FAIL}FAIL{END} datablock round-trip produced a diff:")
        print(_diff(original, rebuilt))

    # Sanity: UUID entity-refs survived the trip (enemy_01 patrols 2 waypoints).
    sc = bpy.data.scenes.get("level1")
    enemy = next((o for o in sc.collection.all_objects if o.name == "enemy_01"), None)
    if enemy is not None and getattr(enemy, "blenjs_has_Patrol", False):
        wps = list(getattr(enemy, "blenjs_Patrol").waypoints)
        if len(wps) == 2 and all(w.target is not None for w in wps):
            print(f"{OK}PASS{END} entity-ref waypoints resolved to objects on import")
        else:
            failures += 1
            print(f"{FAIL}FAIL{END} waypoints did not resolve ({len(wps)} items)")
    else:
        failures += 1
        print(f"{FAIL}FAIL{END} enemy_01 / Patrol not found after import")

    print()
    if failures:
        print(f"{FAIL}{failures} check(s) failed{END}")
        return 1
    print(f"{OK}all Blender datablock round-trip checks passed{END}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
