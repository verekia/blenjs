#!/usr/bin/env python3
"""Generate the canonical root ``game.yaml`` for the example platformer.

Authoring the file *through the canonicalizer* guarantees the committed YAML is
already in canonical form, so the Blender no-op round-trip is a zero diff by
construction. Run with::

    python3 blender/tools/gen_game_yaml.py
    # or: bun run gen:yaml
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.abspath(os.path.join(HERE, "..", "blenjs_addon"))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ADDON)  # import io_yaml directly, bypassing the bpy-laden package __init__

import io_yaml  # noqa: E402

SCHEMA_PATH = os.path.join(ROOT, "generated", "components.schema.json")
OUT_PATH = os.path.join(ROOT, "game.yaml")


def transform(pos, scale=None):
    t = {"pos": pos}
    if scale is not None:
        t["scale"] = scale
    return t


# A small, fully playable level laid out in the XY plane (X horizontal, Y up).
# Coins reward platforming; the goal sits on the ground so the level is always
# completable. UUID keys are stable identity (never names).
LEVEL1 = {
    # --- solid blockout geometry (parametric boxes, no .glb) ---
    "0a10c0de": {"name": "ground", "Transform": transform([9, 0, 0], [24, 1, 4]), "Collider": {"shape": "box"}},
    "1b20d1ef": {"name": "platform_a", "Transform": transform([5, 2, 0], [3, 0.5, 3]), "Collider": {"shape": "box"}},
    "2c30e2fa": {"name": "platform_b", "Transform": transform([10, 3.5, 0], [3, 0.5, 3]), "Collider": {"shape": "box"}},
    "3d40f30b": {"name": "platform_c", "Transform": transform([15, 2.5, 0], [3, 0.5, 3]), "Collider": {"shape": "box"}},
    # --- collectibles ---
    "4e5101ac": {"name": "gem_01", "Transform": transform([2, 1.3, 0]), "Pickup": {"kind": "gem", "value": 25}},
    "5f6102bd": {"name": "coin_01", "Transform": transform([5, 3, 0]), "Pickup": {"kind": "coin", "value": 10}},
    "6071a3ce": {"name": "coin_02", "Transform": transform([10, 4.6, 0]), "Pickup": {"kind": "coin", "value": 10}},
    "7182b4df": {"name": "coin_03", "Transform": transform([15, 3.5, 0]), "Pickup": {"kind": "coin", "value": 10}},
    # --- enemy 1: patrols the ground between two waypoints ---
    "81a2c5e0": {
        "name": "enemy_01",
        "Transform": transform([7, 0.9, 0]),
        "Enemy": {"health": 3},
        "Damageable": {"health": 3},
        "Patrol": {"waypoints": ["91b2c6f1", "a1c2d7e2"]},
    },
    "91b2c6f1": {"name": "wp_a1", "Transform": transform([4, 0.9, 0])},
    "a1c2d7e2": {"name": "wp_a2", "Transform": transform([10, 0.9, 0])},
    # --- enemy 2: patrols on top of platform_b ---
    "b1d2e8f3": {
        "name": "enemy_02",
        "Transform": transform([10, 4, 0]),
        "Enemy": {"health": 3},
        "Damageable": {"health": 3},
        "Patrol": {"speed": 1.5, "waypoints": ["c1e2f9a4", "d1f20ab5"]},
    },
    "c1e2f9a4": {"name": "wp_b1", "Transform": transform([8.7, 4, 0])},
    "d1f20ab5": {"name": "wp_b2", "Transform": transform([11.3, 4, 0])},
    # --- spawn + goal ---
    "e10a1bc6": {"name": "spawn", "Transform": transform([0, 1.5, 0]), "PlayerSpawn": {}},
    "f01a2cd7": {"name": "goal", "Transform": transform([19, 1, 0]), "Goal": {}},
}

DATA = {
    "version": 1,
    "scenes": {
        "level1": {"entities": LEVEL1},
        "level2": {"entities": {}},
    },
}


def main():
    schema = io_yaml.Schema.load(SCHEMA_PATH)
    text = io_yaml.canonical_yaml(DATA, schema)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"✓ wrote {OUT_PATH} ({len(text)} bytes, {len(LEVEL1)} entities in level1)")


if __name__ == "__main__":
    main()
