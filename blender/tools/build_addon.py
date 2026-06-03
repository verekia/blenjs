#!/usr/bin/env python3
"""Package the BlenJS add-on into a zip for Blender's "Install from Disk".

The add-on is project-agnostic: the zip carries only Python code. Everything it reads — the
schema, the prefab manifest, the models — is resolved at load time relative to the project
root (the folder containing the .blen.json you load), never relative to where the add-on is
installed. Run::

    python3 blender/tools/build_addon.py
"""

import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ADDON_SRC = os.path.join(ROOT, "blender", "blenjs_addon")
DIST = os.path.join(ROOT, "blender", "dist")
OUT = os.path.join(DIST, "blenjs_addon.zip")


def main():
    os.makedirs(DIST, exist_ok=True)
    if os.path.exists(OUT):
        os.remove(OUT)

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _dirnames, filenames in os.walk(ADDON_SRC):
            if "__pycache__" in dirpath:
                continue
            for fn in filenames:
                if fn.endswith(".pyc") or fn.endswith(".json"):  # code only — no project data
                    continue
                abs_path = os.path.join(dirpath, fn)
                rel = os.path.relpath(abs_path, os.path.dirname(ADDON_SRC))
                z.write(abs_path, rel)

    print(f"✓ wrote {OUT}")
    print("  Install in Blender: Edit > Preferences > Add-ons > Install from Disk… > select this zip.")


if __name__ == "__main__":
    main()
