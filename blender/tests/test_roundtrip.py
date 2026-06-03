#!/usr/bin/env python3
"""The acceptance test the spec calls critical (§6, §11):

    load .blen.json -> save untouched -> ZERO diff.

If the no-op round-trip is not byte-stable, nothing downstream is trustworthy.
This runs the *canonicalization core* of the add-on (``io_json``) outside Blender
— it does not require bpy — so CI can guard it. It also checks idempotency and
that genuinely messy input normalizes to the exact same canonical bytes.

Run with::

    python3 blender/tests/test_roundtrip.py     # or: bun run test:roundtrip
"""

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.abspath(os.path.join(HERE, "..", "blenjs_addon"))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ADDON)

import io_json  # noqa: E402

SCHEMA_PATH = os.path.join(ROOT, "generated", "components.schema.json")
GAME_PATH = os.path.join(ROOT, "platformer.blen.json")

FAIL = "\033[31m"
OK = "\033[32m"
END = "\033[0m"


def _diff(a: str, b: str) -> str:
    import difflib

    return "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), "expected", "actual"))


def main() -> int:
    schema = io_json.Schema.load(SCHEMA_PATH)
    with open(GAME_PATH, "r", encoding="utf-8") as f:
        original = f.read()

    failures = 0

    # 1) Zero-diff no-op round-trip: load -> canonicalize -> dump == original bytes.
    data = io_json.loads(original)
    out = io_json.canonical_json(data, schema)
    if out == original:
        print(f"{OK}PASS{END} no-op round-trip is byte-stable (zero diff)")
    else:
        failures += 1
        print(f"{FAIL}FAIL{END} no-op round-trip produced a diff:")
        print(_diff(original, out))

    # 2) Idempotency: canonicalizing the canonical output changes nothing.
    out2 = io_json.canonical_json(io_json.loads(out), schema)
    if out2 == out:
        print(f"{OK}PASS{END} canonicalization is idempotent")
    else:
        failures += 1
        print(f"{FAIL}FAIL{END} canonicalization is not idempotent:")
        print(_diff(out, out2))

    # 3) Normalization: deliberately messy but semantically-equivalent input must
    #    canonicalize to the exact same bytes (proves sorting / default-fill /
    #    float quantization / key ordering actually do work).
    messy = copy.deepcopy(data)
    ents = messy["scenes"]["level1"]["entities"]
    # reverse entity order
    messy["scenes"]["level1"]["entities"] = {k: ents[k] for k in reversed(list(ents.keys()))}
    ents = messy["scenes"]["level1"]["entities"]
    # drop default fields on PLAIN entities that must be refilled
    del ents["0a10c0de"]["Transform"]["rot"]
    del ents["91b2c6f1"]["Transform"]["scale"]
    # whole-number floats (9 -> 9.0) and a long-tail float must quantize
    ents["0a10c0de"]["Transform"]["pos"] = [9.0, 0.0, 0.0]
    ents["3d40f30b"]["Transform"]["pos"] = [15.00001, 0.0, 2.5]
    # reorder keys within a PLAIN entity (components before name/Transform -> name first,
    # Transform next, then components alpha: Collider, Material)
    g = ents["0a10c0de"]
    ents["0a10c0de"] = {"Collider": g["Collider"], "Material": g["Material"], "name": g["name"], "Transform": g["Transform"]}
    # reorder keys within a PREFAB INSTANCE: name/prefab/Transform/overrides must re-sort,
    # and sparse overrides must NOT gain default fields (Patrol.speed/loop stay inherited).
    en = ents["81a2c5e0"]
    ents["81a2c5e0"] = {"Patrol": en["Patrol"], "Transform": en["Transform"], "prefab": en["prefab"], "name": en["name"]}
    messy_out = io_json.canonical_json(messy, schema)
    if messy_out == original:
        print(f"{OK}PASS{END} messy input normalizes to canonical bytes")
    else:
        failures += 1
        print(f"{FAIL}FAIL{END} messy input did not normalize:")
        print(_diff(original, messy_out))

    print()
    if failures:
        print(f"{FAIL}{failures} check(s) failed{END}")
        return 1
    print(f"{OK}all round-trip checks passed{END}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
