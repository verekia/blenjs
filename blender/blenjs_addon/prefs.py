"""Add-on preferences: where to find components.schema.json."""

import bpy
from bpy.props import StringProperty


class BLENJS_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__.partition(".")[0]

    schema_path: StringProperty(
        name="components.schema.json",
        subtype="FILE_PATH",
        description="Path to your repo's generated/components.schema.json (the codegen output)",
        default="",
    )

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "schema_path")
        col.label(text="Point this at generated/components.schema.json, then reload the add-on.")
        col.label(text="(If left empty, BlenJS looks for a bundled copy or a repo-relative path.)")
