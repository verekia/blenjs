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


def transform(pos, scale=None, rot=None):
    t = {"pos": pos}
    if rot is not None:
        t["rot"] = rot
    if scale is not None:
        t["scale"] = scale
    return t


# Authored surface colours for the parametric blockout (the `Material` component). RGB is
# 0–1 sRGB — what you'd pick in Blender's colour swatch — matching the old hardcoded look
# (#39424f platforms, #d946ef goal) but now as data the runtime reads. Only `color` is given;
# the canonicalizer fills opacity/unlit defaults.
BLOCKOUT = {"color": [0.2235, 0.2588, 0.3098]}
GOAL_MAT = {"color": [0.851, 0.2745, 0.9373]}
RUNE_MAT = {"color": [0.13, 0.83, 0.93], "opacity": 0.35}  # translucent pad so a Trigger is visible

# Scene lighting + camera, authored as ordinary entities that the Blender add-on turns into REAL
# datablocks (a Sun lamp, a Camera, the World) so the viewport frames + lights like the game.
# Ambient drives the World (position/rotation ignored). The directional "sun" emits along its
# local -Z, so its Transform.rot is the light direction (shared by Blender and the runtime); its
# position is just where the gizmo sits. The camera looks +Y with +Z up, which is rot=[pi/2,0,0].
AMBIENT = {"type": "ambient", "intensity": 0.9}
SUN = {"type": "directional", "intensity": 2}
SUN_ROT = [0.6, -0.4, 0]  # a 3/4 key light from upper-front (emits down, into the scene, +X)
CAMERA_ROT = [1.5708, 0, 0]  # pi/2 about X: the default -Z view becomes +Y, up becomes +Z


# A small, fully playable level laid out in the XZ plane (X horizontal, Z up, Y
# depth) — Z-up right-handed, the same frame as Blender. Platforms stay parametric
# boxes (Collider, no model) carrying an authored Material colour; coins/gem/enemies are
# PREFAB INSTANCES (model + data from prefabs/<name>.json) carrying only their per-instance
# overrides. The goal sits on the ground so the level is always completable. Light/Camera are
# authored entities. UUID keys are stable identity.
LEVEL1 = {
    # --- solid blockout geometry (parametric boxes, no model) ---
    "0a10c0de": {"name": "ground", "Transform": transform([9, 0, 0], [24, 4, 1]), "Collider": {"shape": "box"}, "Material": BLOCKOUT},
    "1b20d1ef": {"name": "platform_a", "Transform": transform([5, 0, 2], [3, 3, 0.5]), "Collider": {"shape": "box"}, "Material": BLOCKOUT},
    "2c30e2fa": {"name": "platform_b", "Transform": transform([10, 0, 3.5], [3, 3, 0.5]), "Collider": {"shape": "box"}, "Material": BLOCKOUT},
    "3d40f30b": {"name": "platform_c", "Transform": transform([15, 0, 2.5], [3, 3, 0.5]), "Collider": {"shape": "box"}, "Material": BLOCKOUT},
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
    "f01a2cd7": {"name": "goal", "Transform": transform([19, 0, 1]), "Goal": {}, "Material": GOAL_MAT},
    # --- authored lighting + camera ---
    "fa000001": {"name": "ambient_light", "Transform": transform([0, 0, 0]), "Light": AMBIENT},
    "fb000002": {"name": "sun", "Transform": transform([2, -6, 10], rot=SUN_ROT), "Light": SUN},
    "fc000003": {"name": "camera", "Transform": transform([0, -16, 3], rot=CAMERA_ROT), "Camera": {}},
    # --- event wiring: an invisible kill volume (replaces the old FALL_KILL_Z constant) + a
    #     visible rune that removes BOTH enemies when stepped on (Trigger.targets = entityRef wiring)
    "fd000004": {"name": "kill_zone", "Transform": transform([9, 0, -18], [64, 24, 10]), "Trigger": {"action": "lose"}},
    "fe000005": {
        "name": "enemy_rune",
        "Transform": transform([12, 0, 0.55], [2, 4, 0.3]),
        "Trigger": {"action": "remove", "targets": ["81a2c5e0", "b1d2e8f3"]},
        "Material": RUNE_MAT,
    },
    # --- shaped colliders off the critical path: a sphere "boulder" behind the spawn and a
    #     capsule "pillar" past the goal — they exercise the sphere/capsule physics and show the
    #     Blender collider overlay drawing non-box shapes (box stays the default for platforms) ---
    "ff000006": {
        "name": "boulder",
        "Transform": transform([-1.5, 0, 1.25], [1.5, 1.5, 1.5]),
        "Collider": {"shape": "sphere"},
        "Material": {"color": [0.55, 0.45, 0.35]},
    },
    "ff000007": {
        "name": "pillar",
        "Transform": transform([21, 0, 2], [1.2, 1.2, 3]),
        "Collider": {"shape": "capsule"},
        "Material": {"color": [0.45, 0.5, 0.55]},
    },
}

# A second, shorter level — proves the scene switcher and the "clear a level → advance" flow.
LEVEL2 = {
    "201a0001": {"name": "ground_start", "Transform": transform([3, 0, 0], [12, 4, 1]), "Collider": {"shape": "box"}, "Material": BLOCKOUT},
    "201a0002": {"name": "ground_mid", "Transform": transform([15, 0, 0], [8, 4, 1]), "Collider": {"shape": "box"}, "Material": BLOCKOUT},
    "201a0003": {"name": "step_1", "Transform": transform([17, 0, 1.4], [3, 3, 0.5]), "Collider": {"shape": "box"}, "Material": BLOCKOUT},
    "201a0004": {"name": "step_2", "Transform": transform([20, 0, 2.8], [3, 3, 0.5]), "Collider": {"shape": "box"}, "Material": BLOCKOUT},
    "201a0005": {"name": "spawn", "Transform": transform([0, 0, 1.5]), "PlayerSpawn": {}},
    "201a0006": {"name": "goal", "Transform": transform([20, 0, 3.5]), "Goal": {}, "Material": GOAL_MAT},
    "201a0007": {"name": "coin_01", "prefab": "coin", "Transform": transform([3, 0, 1.6])},
    "201a0008": {"name": "coin_02", "prefab": "coin", "Transform": transform([13, 0, 1.6])},
    "201a0009": {"name": "coin_03", "prefab": "coin", "Transform": transform([17, 0, 2.4])},
    "201a000a": {"name": "gem_01", "prefab": "pickup", "Transform": transform([6, 0, 1.4])},
    "201a000b": {
        "name": "enemy_01",
        "prefab": "enemy",
        "Transform": transform([5, 0, 0.9]),
        "Patrol": {"speed": 2.5, "waypoints": ["201a000c", "201a000d"]},
    },
    "201a000c": {"name": "wp_a1", "Transform": transform([1, 0, 0.9])},
    "201a000d": {"name": "wp_a2", "Transform": transform([8, 0, 0.9])},
    "201a000e": {
        "name": "enemy_02",
        "prefab": "enemy",
        "Transform": transform([14, 0, 0.9]),
        # speed omitted — it equals the prefab default (2), so it is inherited, not overridden.
        # (Keeping it would make the committed file disagree with Blender's diff-based export.)
        "Patrol": {"waypoints": ["201a000f", "201a0010"]},
    },
    "201a000f": {"name": "wp_b1", "Transform": transform([11.5, 0, 0.9])},
    "201a0010": {"name": "wp_b2", "Transform": transform([18, 0, 0.9])},
    # --- authored lighting + camera ---
    "201a00f1": {"name": "ambient_light", "Transform": transform([0, 0, 0]), "Light": AMBIENT},
    "201a00f2": {"name": "sun", "Transform": transform([2, -6, 10], rot=SUN_ROT), "Light": SUN},
    "201a00f3": {"name": "camera", "Transform": transform([0, -16, 3], rot=CAMERA_ROT), "Camera": {}},
    "201a00f4": {"name": "kill_zone", "Transform": transform([11, 0, -18], [64, 24, 10]), "Trigger": {"action": "lose"}},
    "201a00f5": {
        "name": "enemy_rune",
        "Transform": transform([10, 0, 0.55], [2, 4, 0.3]),
        "Trigger": {"action": "remove", "targets": ["201a000b", "201a000e"]},
        "Material": RUNE_MAT,
    },
}

# Blender object names are globally unique across the whole .blend, so two scenes cannot share a
# name — the second would import as "spawn.001" and the round-trip would no longer be zero-diff.
# Namespace level2 so every name is unique across the project. Identity is by UUID; names are
# cosmetic (principle #5), so this is purely to keep the multi-scene example round-trip clean.
for _ent in LEVEL2.values():
    _ent["name"] = "l2_" + _ent["name"]

DATA = {
    "version": 1,
    "scenes": {
        "level1": {"entities": LEVEL1},
        "level2": {"entities": LEVEL2},
    },
}


def main():
    schema = io_json.Schema.load(SCHEMA_PATH)
    text = io_json.canonical_json(DATA, schema)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"✓ wrote {OUT_PATH} ({len(text)} bytes, {len(LEVEL1)} in level1, {len(LEVEL2)} in level2)")


if __name__ == "__main__":
    main()
