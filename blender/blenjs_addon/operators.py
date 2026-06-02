"""Operators: import, export (the Cmd/Ctrl+S target), and component editing."""

import os

import bpy
from bpy.props import CollectionProperty, IntProperty, StringProperty

from . import scenes, schema
from .uuids import ensure_uuid


class BLENJS_OT_import_json(bpy.types.Operator):
    bl_idname = "blenjs.import_json"
    bl_label = "Import BlenJS JSON"
    bl_description = "Load all scenes from a BlenJS game.json"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH")
    directory: StringProperty(subtype="DIR_PATH")
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        # Drag-drop (FileHandler) sets directory+files; import straight away.
        if (self.files and self.directory) or self.filepath:
            return self.execute(context)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        path = self.filepath
        if not path and self.files and self.directory:
            path = os.path.join(self.directory, self.files[0].name)
        if not path:
            self.report({"ERROR"}, "No file path provided")
            return {"CANCELLED"}
        try:
            scenes.import_game(path, context)
        except Exception as e:  # noqa: BLE001 — surface any import problem to the user
            self.report({"ERROR"}, f"BlenJS import failed: {e}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"BlenJS loaded {os.path.basename(path)}")
        return {"FINISHED"}


class BLENJS_OT_export(bpy.types.Operator):
    bl_idname = "blenjs.export"
    bl_label = "Save BlenJS JSON"
    bl_description = "Write canonical JSON back to the file this game was loaded from"
    bl_options = {"REGISTER"}

    def execute(self, context):
        path = context.window_manager.blenjs_filepath
        if not path:
            self.report({"WARNING"}, "No game.json loaded — drag one into the viewport first")
            return {"CANCELLED"}
        try:
            scenes.export_to_path(path)
        except Exception as e:  # noqa: BLE001
            self.report({"ERROR"}, f"BlenJS save failed: {e}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"BlenJS saved {os.path.basename(path)}")
        return {"FINISHED"}


class BLENJS_OT_add_component(bpy.types.Operator):
    bl_idname = "blenjs.add_component"
    bl_label = "Add Component"
    bl_options = {"REGISTER", "UNDO"}

    component: StringProperty()

    def execute(self, context):
        obj = context.object
        if not obj:
            return {"CANCELLED"}
        ensure_uuid(obj)
        setattr(obj, schema.component_active_name(self.component), True)
        return {"FINISHED"}


class BLENJS_OT_remove_component(bpy.types.Operator):
    bl_idname = "blenjs.remove_component"
    bl_label = "Remove Component"
    bl_options = {"REGISTER", "UNDO"}

    component: StringProperty()

    def execute(self, context):
        obj = context.object
        if not obj:
            return {"CANCELLED"}
        setattr(obj, schema.component_active_name(self.component), False)
        return {"FINISHED"}


class BLENJS_OT_ref_add(bpy.types.Operator):
    bl_idname = "blenjs.ref_add"
    bl_label = "Add Reference"
    bl_options = {"REGISTER", "UNDO"}

    component: StringProperty()
    field: StringProperty()

    def execute(self, context):
        obj = context.object
        pg = getattr(obj, schema.component_pg_name(self.component))
        coll = getattr(pg, self.field)
        coll.add()
        setattr(pg, f"{self.field}_index", len(coll) - 1)
        return {"FINISHED"}


class BLENJS_OT_ref_remove(bpy.types.Operator):
    bl_idname = "blenjs.ref_remove"
    bl_label = "Remove Reference"
    bl_options = {"REGISTER", "UNDO"}

    component: StringProperty()
    field: StringProperty()

    def execute(self, context):
        obj = context.object
        pg = getattr(obj, schema.component_pg_name(self.component))
        coll = getattr(pg, self.field)
        idx = getattr(pg, f"{self.field}_index")
        if 0 <= idx < len(coll):
            coll.remove(idx)
            setattr(pg, f"{self.field}_index", max(0, idx - 1))
        return {"FINISHED"}


def menu_import(self, context):
    self.layout.operator(BLENJS_OT_import_json.bl_idname, text="BlenJS Game (.json)")


CLASSES = (
    BLENJS_OT_import_json,
    BLENJS_OT_export,
    BLENJS_OT_add_component,
    BLENJS_OT_remove_component,
    BLENJS_OT_ref_add,
    BLENJS_OT_ref_remove,
)
