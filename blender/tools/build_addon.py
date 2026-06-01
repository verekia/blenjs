#!/usr/bin/env python3
"""Package the BlenJS add-on into a zip for Blender's "Install from Disk".

Bundles a copy of generated/components.schema.json next to the add-on so it works
out of the box (no repo-relative path or preference needed). Run::

    python3 blender/tools/build_addon.py
"""

import os
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ADDON_SRC = os.path.join(ROOT, "blender", "blenjs_addon")
SCHEMA = os.path.join(ROOT, "generated", "components.schema.json")
DIST = os.path.join(ROOT, "blender", "dist")
OUT = os.path.join(DIST, "blenjs_addon.zip")


def main():
    if not os.path.isfile(SCHEMA):
        raise SystemExit("generated/components.schema.json missing — run `bun run codegen` first.")
    os.makedirs(DIST, exist_ok=True)

    if os.path.exists(OUT):
        os.remove(OUT)

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(ADDON_SRC):
            if "__pycache__" in dirpath:
                continue
            for fn in filenames:
                if fn.endswith(".pyc"):
                    continue
                abs_path = os.path.join(dirpath, fn)
                rel = os.path.relpath(abs_path, os.path.dirname(ADDON_SRC))
                z.write(abs_path, rel)
        # bundle the schema inside the add-on package
        z.write(SCHEMA, os.path.join("blenjs_addon", "components.schema.json"))

    print(f"✓ wrote {OUT}")
    print("  Install in Blender: Edit > Preferences > Add-ons > Install from Disk… > select this zip.")


if __name__ == "__main__":
    main()
