"""Drag-and-drop a .blen.json onto Blender -> import operator (spec §6.1).

The FileHandler API requires a recent Blender (4.1+); the minimum is pinned in ``bl_info``.
Blender matches a drop by the file's LAST extension only (``.json`` for ``foo.blen.json``),
so ``bl_file_extensions`` must be ``.json``; we then narrow to BlenJS projects
(``*.blen.json``) inside the import operator, which sees the full path. Plain ``.json`` drops
are ignored there.
"""

import bpy


class BLENJS_FH_blen_json(bpy.types.FileHandler):
    bl_idname = "BLENJS_FH_blen_json"
    bl_label = "BlenJS Project"
    bl_import_operator = "blenjs.import_json"
    bl_file_extensions = ".json"

    @classmethod
    def poll_drop(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D"
