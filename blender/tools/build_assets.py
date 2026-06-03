#!/usr/bin/env python3
"""Build the web-ready assets for BlenJS prefabs/models. Run INSIDE Blender::

    blender --background --factory-startup --python blender/tools/build_assets.py
    # or: bun run build:models

Two outputs, both committed (so the web build never needs Blender):

  1. ``prefabs/<name>.blend``  ->  ``app/public/assets/<name>.glb``
     Exported as GLB with **modifiers applied** (e.g. the Mirror on coin/enemy/player)
     and kept **Z-up** (``export_yup=False``) so the geometry lands in the game's Z-up
     world with no runtime rotation (the runtime sets ``Object3D.DEFAULT_UP = +Z``).

  2. ``prefabs/*.json``  ->  ``generated/prefabs.json``
     One aggregated manifest (prefab name -> {name, components}) imported by the R3F
     runtime (resolvePrefabs) and read by the Blender add-on (visualization + override
     diffing). Component names are validated against ``generated/components.schema.json``.

This script needs ``bpy`` so it runs in Blender; the manifest step is plain stdlib.
"""

import glob
import json
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PREFABS_DIR = os.path.join(ROOT, "prefabs")
ASSETS_DIR = os.path.join(ROOT, "app", "public", "assets")
SCHEMA_PATH = os.path.join(ROOT, "generated", "components.schema.json")
MANIFEST_OUT = os.path.join(ROOT, "generated", "prefabs.json")

RESERVED_KEYS = {"name", "Transform"}  # Transform is always valid; name is identity


# --------------------------------------------------------------------------- #
# 1. .blend -> .glb
# --------------------------------------------------------------------------- #
def export_glb(blend_path: str, out_path: str) -> None:
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        export_apply=True,  # apply modifiers (Mirror, etc.) onto a temporary copy
        export_yup=False,  # keep Blender Z-up -> matches the game world, no +90deg hack
        use_active_scene=True,
        export_materials="EXPORT",  # carry the Principled base colours into the glTF
        export_extras=False,
    )


def build_models() -> list:
    os.makedirs(ASSETS_DIR, exist_ok=True)
    blends = sorted(glob.glob(os.path.join(PREFABS_DIR, "*.blend")))
    built = []
    for blend in blends:
        name = os.path.splitext(os.path.basename(blend))[0]
        out = os.path.join(ASSETS_DIR, f"{name}.glb")
        try:
            export_glb(blend, out)
            size = os.path.getsize(out)
            built.append((name, size))
            print(f"  [glb] {name}.blend -> app/public/assets/{name}.glb ({size} bytes)")
        except Exception as e:  # noqa: BLE001 — report and keep going
            print(f"  [glb] FAILED {name}.blend: {e}")
    return built


# --------------------------------------------------------------------------- #
# 2. prefabs/*.json -> generated/prefabs.json
# --------------------------------------------------------------------------- #
def _known_components() -> set:
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            doc = json.load(f)
        return {c["name"] for c in doc.get("components", [])}
    except OSError:
        print(f"  [manifest] WARNING: schema not found at {SCHEMA_PATH}; skipping validation")
        return set()


def build_manifest() -> dict:
    known = _known_components()
    manifest: dict = {}
    for path in sorted(glob.glob(os.path.join(PREFABS_DIR, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        name = data.get("name") or os.path.splitext(os.path.basename(path))[0]
        components = data.get("components") or {}
        if known:
            for cname in components:
                if cname not in RESERVED_KEYS and cname not in known:
                    print(f"  [manifest] WARNING: prefab '{name}' uses unknown component '{cname}'")
        manifest[name] = {"name": name, "components": components}
        print(f"  [manifest] {os.path.basename(path)} -> prefab '{name}' ({len(components)} components)")
    return manifest


def write_manifest(manifest: dict) -> None:
    os.makedirs(os.path.dirname(MANIFEST_OUT), exist_ok=True)
    with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
        f.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"  [manifest] wrote generated/prefabs.json ({len(manifest)} prefabs)")


def main() -> None:
    print("BlenJS build:models")
    print("- exporting prefab glTF -------------------------------------------------")
    built = build_models()
    print("- aggregating prefab manifest ------------------------------------------")
    manifest = build_manifest()
    write_manifest(manifest)
    print(f"Done: {len(built)} glb, {len(manifest)} prefabs.")


if __name__ == "__main__":
    main()
