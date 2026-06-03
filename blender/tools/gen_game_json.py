#!/usr/bin/env python3
"""Generate the canonical example project ``platformer.blen.json``.

A BlenJS project file is named ``<name>.blen.json`` (so one repo can hold several —
``platformer.blen.json``, ``shmup.blen.json`` — sharing the same prefabs/schema/assets).
Authoring the file *through the canonicalizer* guarantees the committed JSON is already in
canonical form, so the Blender no-op round-trip is a zero diff by construction. Run with::

    python3 blender/tools/gen_game_json.py
    # or: bun run gen:json
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.abspath(os.path.join(HERE, "..", "blenjs_addon"))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ADDON)  # import io_json directly, bypassing the bpy-laden package __init__

import io_json  # noqa: E402

SCHEMA_PATH = os.path.join(ROOT, "generated", "components.schema.json")
OUT_PATH = os.path.join(ROOT, "platformer.blen.json")


def transform(pos, scale=None):
    t = {"pos": pos}
    if scale is not None:
        t["scale"] = scale
    return t


# A small, fully playable level laid out in the XZ plane (X horizontal, Z up, Y
# depth) — Z-up right-handed, the same frame as Blender. Platforms stay parametric
# boxes (Collider, no model); coins/gem/enemies are PREFAB INSTANCES (model + data
# from prefabs/<name>.json) carrying only their per-instance overrides. The goal sits
# on the ground so the level is always completable. UUID keys are stable identity.
LEVEL1 = {
    # --- solid blockout geometry (parametric boxes, no model) ---
    "0a10c0de": {"name": "ground", "Transform": transform([9, 0, 0], [24, 4, 1]), "Collider": {"shape": "box"}},
    "1b20d1ef": {"name": "platform_a", "Transform": transform([5, 0, 2], [3, 3, 0.5]), "Collider": {"shape": "box"}},
    "2c30e2fa": {"name": "platform_b", "Transform": transform([10, 0, 3.5], [3, 3, 0.5]), "Collider": {"shape": "box"}},
    "3d40f30b": {"name": "platform_c", "Transform": transform([15, 0, 2.5], [3, 3, 0.5]), "Collider": {"shape": "box"}},
    # --- collectibles (prefab instances; kind/value/scale/model inherited) ---
    "4e5101ac": {"name": "gem_01", "prefab": "pickup", "Transform": transform([2, 0, 1.3])},
    "5f6102bd": {"name": "coin_01", "prefab": "coin", "Transform": transform([5, 0, 3])},
    "6071a3ce": {"name": "coin_02", "prefab": "coin", "Transform": transform([10, 0, 4.6])},
    "7182b4df": {"name": "coin_03", "prefab": "coin", "Transform": transform([15, 0, 3.5])},
    # --- enemy 1: prefab instance; waypoints are a required per-instance override ---
    "81a2c5e0": {
        "name": "enemy_01",
        "prefab": "enemy",
        "Transform": transform([7, 0, 0.9]),
        "Patrol": {"waypoints": ["91b2c6f1", "a1c2d7e2"]},
    },
    "91b2c6f1": {"name": "wp_a1", "Transform": transform([4, 0, 0.9])},
    "a1c2d7e2": {"name": "wp_a2", "Transform": transform([10, 0, 0.9])},
    # --- enemy 2: prefab instance; overrides patrol speed too ---
    "b1d2e8f3": {
        "name": "enemy_02",
        "prefab": "enemy",
        "Transform": transform([10, 0, 4]),
        "Patrol": {"speed": 1.5, "waypoints": ["c1e2f9a4", "d1f20ab5"]},
    },
    "c1e2f9a4": {"name": "wp_b1", "Transform": transform([8.7, 0, 4])},
    "d1f20ab5": {"name": "wp_b2", "Transform": transform([11.3, 0, 4])},
    # --- spawn + goal ---
    "e10a1bc6": {"name": "spawn", "Transform": transform([0, 0, 1.5]), "PlayerSpawn": {}},
    "f01a2cd7": {"name": "goal", "Transform": transform([19, 0, 1]), "Goal": {}},
}

DATA = {
    "version": 1,
    "scenes": {
        "level1": {"entities": LEVEL1},
        "level2": {"entities": {}},
    },
}


def main():
    schema = io_json.Schema.load(SCHEMA_PATH)
    text = io_json.canonical_json(DATA, schema)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"✓ wrote {OUT_PATH} ({len(text)} bytes, {len(LEVEL1)} entities in level1)")


if __name__ == "__main__":
    main()
