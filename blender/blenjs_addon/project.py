"""BlenJS project conventions — where the add-on finds a project's files.

A project file is named ``<name>.blen.json`` (e.g. ``platformer.blen.json``); its folder is
the project root, and everything the add-on reads is resolved relative to it. Several project
files can share one root — and therefore one set of prefabs/schema/assets:

    <root>/platformer.blen.json               a project (scenes) you load/save
    <root>/shmup.blen.json                     …another, sharing the resources below
    <root>/prefabs/<name>.{json,blend}        prefab data + editable model source
    <root>/generated/components.schema.json   the schema (bun run codegen)
    <root>/generated/prefabs.json             the prefab manifest (bun run build:models)
    <root>/app/public/assets/<name>.glb       the built models (bun run build:models)

No ``bpy`` import (stdlib only) so it stays unit-testable outside Blender.
"""

import os

# Built-glTF directory, tried in order under the project root. The first that exists wins;
# `app/public/assets` is the canonical location (the web app's static-served folder).
ASSET_DIRS = ("app/public/assets", "public/assets", "assets")


def root_of(project_path: str) -> str:
    """The project root: the folder containing the loaded ``.blen.json`` file."""
    return os.path.dirname(os.path.abspath(project_path))


def schema_path(root: str) -> str:
    return os.path.join(root, "generated", "components.schema.json")


def prefabs_path(root: str) -> str:
    return os.path.join(root, "generated", "prefabs.json")


def assets_dir(root: str) -> str:
    for rel in ASSET_DIRS:
        d = os.path.join(root, *rel.split("/"))
        if os.path.isdir(d):
            return d
    return os.path.join(root, *ASSET_DIRS[0].split("/"))  # canonical default (may not exist yet)
