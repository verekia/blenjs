"""Drag-and-drop a .yaml onto Blender -> import operator (spec §6.1).

The FileHandler API requires a recent Blender (4.1+); the minimum is pinned in
``bl_info`` and documented in the add-on README.
"""

import bpy


class BLENJS_FH_yaml(bpy.types.FileHandler):
    bl_idname = "BLENJS_FH_yaml"
    bl_label = "BlenJS YAML"
    bl_import_operator = "blenjs.import_yaml"
    bl_file_extensions = ".yaml;.yml"

    @classmethod
    def poll_drop(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D"
