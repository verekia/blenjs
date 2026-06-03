"""BlenJS — Blender as the level editor for R3F games.

Drag a ``<name>.blen.json`` project into the viewport to load all scenes as Blender
Scene datablocks; edit components in Object Properties > BlenJS; press Cmd/Ctrl+S to
write canonical JSON back to the original path. No ``.blend`` is ever saved.
"""

bl_info = {
    "name": "BlenJS",
    "author": "BlenJS",
    "version": (0, 1, 0),
    "blender": (4, 1, 0),  # FileHandler drag-and-drop API
    "location": "Drag a .blen.json into the viewport · Object Properties > BlenJS",
    "description": "Blender-as-editor for React Three Fiber games: load/save canonical .blen.json.",
    "category": "Import-Export",
}

import bpy
from bpy.props import BoolProperty, StringProperty

from . import file_handler, keymap, operators, panels, schema


def register() -> None:
    # Where the loaded game lives (stash for Cmd/Ctrl+S), and which scenes are ours.
    bpy.types.WindowManager.blenjs_filepath = StringProperty(name="BlenJS file", default="", subtype="FILE_PATH")
    bpy.types.Scene.blenjs_managed = BoolProperty(name="BlenJS managed scene", default=False)

    # Register the static part only; the schema-driven PropertyGroups are built per project
    # by schema.apply_schema() when a .blen.json is loaded (see project.py).
    schema.register()

    for cls in operators.CLASSES:
        bpy.utils.register_class(cls)
    for cls in panels.CLASSES:
        bpy.utils.register_class(cls)
    bpy.utils.register_class(file_handler.BLENJS_FH_blen_json)

    bpy.types.TOPBAR_MT_file_import.append(operators.menu_import)
    keymap.register()


def unregister() -> None:
    keymap.unregister()
    bpy.types.TOPBAR_MT_file_import.remove(operators.menu_import)

    bpy.utils.unregister_class(file_handler.BLENJS_FH_blen_json)
    for cls in reversed(panels.CLASSES):
        bpy.utils.unregister_class(cls)
    for cls in reversed(operators.CLASSES):
        bpy.utils.unregister_class(cls)

    schema.unregister()

    del bpy.types.Scene.blenjs_managed
    del bpy.types.WindowManager.blenjs_filepath


if __name__ == "__main__":
    register()
