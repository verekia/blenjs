"""BlenJS — Blender as the level editor for R3F games.

Drag a ``game.yaml`` into the viewport to load all scenes as Blender Scene
datablocks; edit components in Object Properties > BlenJS; press Cmd/Ctrl+S to
write canonical YAML back to the original path. No ``.blend`` is ever saved.
"""

bl_info = {
    "name": "BlenJS",
    "author": "BlenJS",
    "version": (0, 1, 0),
    "blender": (4, 1, 0),  # FileHandler drag-and-drop API
    "location": "Drag game.yaml into the viewport · Object Properties > BlenJS",
    "description": "Blender-as-editor for React Three Fiber games: load/save canonical game.yaml.",
    "category": "Import-Export",
}

import bpy
from bpy.props import BoolProperty, StringProperty

from . import file_handler, keymap, operators, panels, prefs, schema


def register() -> None:
    bpy.utils.register_class(prefs.BLENJS_AddonPreferences)

    # Where the loaded game lives (stash for Cmd/Ctrl+S), and which scenes are ours.
    bpy.types.WindowManager.blenjs_filepath = StringProperty(name="BlenJS file", default="", subtype="FILE_PATH")
    bpy.types.Scene.blenjs_managed = BoolProperty(name="BlenJS managed scene", default=False)

    # Dynamic, schema-driven PropertyGroups + per-object slots.
    schema.register()

    for cls in operators.CLASSES:
        bpy.utils.register_class(cls)
    for cls in panels.CLASSES:
        bpy.utils.register_class(cls)
    bpy.utils.register_class(file_handler.BLENJS_FH_yaml)

    bpy.types.TOPBAR_MT_file_import.append(operators.menu_import)
    keymap.register()


def unregister() -> None:
    keymap.unregister()
    bpy.types.TOPBAR_MT_file_import.remove(operators.menu_import)

    bpy.utils.unregister_class(file_handler.BLENJS_FH_yaml)
    for cls in reversed(panels.CLASSES):
        bpy.utils.unregister_class(cls)
    for cls in reversed(operators.CLASSES):
        bpy.utils.unregister_class(cls)

    schema.unregister()

    del bpy.types.Scene.blenjs_managed
    del bpy.types.WindowManager.blenjs_filepath
    bpy.utils.unregister_class(prefs.BLENJS_AddonPreferences)


if __name__ == "__main__":
    register()
