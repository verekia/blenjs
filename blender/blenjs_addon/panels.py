"""Inspector panel, Add Component menu, and the entity-ref UIList (spec §6.3, §6.4)."""

import bpy

from . import schema


class BLENJS_UL_object_refs(bpy.types.UIList):
    """List of object references for an entity-ref array field (drag-to-assign)."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "target", text="", emboss=True, icon="OBJECT_DATA")


class BLENJS_MT_add_component(bpy.types.Menu):
    bl_idname = "BLENJS_MT_add_component"
    bl_label = "Add Component"

    def draw(self, context):
        layout = self.layout
        obj = context.object
        by_category: dict = {}
        for comp in schema.behavior_or_data_components():
            by_category.setdefault(comp["category"], []).append(comp)

        for category in sorted(by_category):
            layout.label(text=category)
            for comp in by_category[category]:
                name = comp["name"]
                active = getattr(obj, schema.component_active_name(name), False)
                row = layout.row()
                row.enabled = not active
                op = row.operator("blenjs.add_component", text=name, icon="DOT" if active else "ADD")
                op.component = name
            layout.separator()


def _draw_component(layout, component: dict, pg, obj):
    for field in component.get("fields", []):
        name = field["name"]
        if field.get("type") == "array" and field.get("itemType") == "entityRef":
            layout.label(text=field.get("tooltip", name) or name)
            row = layout.row()
            row.template_list("BLENJS_UL_object_refs", f"{component['name']}_{name}", pg, name, pg, f"{name}_index", rows=2)
            col = row.column(align=True)
            add = col.operator("blenjs.ref_add", text="", icon="ADD")
            add.component, add.field = component["name"], name
            rem = col.operator("blenjs.ref_remove", text="", icon="REMOVE")
            rem.component, rem.field = component["name"], name
        else:
            layout.prop(pg, name)


class BLENJS_PT_inspector(bpy.types.Panel):
    bl_label = "BlenJS"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        layout = self.layout
        obj = context.object
        if obj is None:
            layout.label(text="No active object")
            return

        sch = schema.get_schema()
        if sch is None:
            layout.label(text="Schema not loaded", icon="ERROR")
            layout.label(text="Set the path in add-on preferences.")
            return

        col = layout.column(align=True)
        col.label(text=f"UUID: {obj.get('blenjs_uuid', '') or '(stamped on save)'}", icon="KEYINGSET")
        col.label(text="Transform is the native object transform.", icon="ORIENTATION_LOCAL")

        layout.menu("BLENJS_MT_add_component", icon="ADD")

        for comp in schema.behavior_or_data_components():
            name = comp["name"]
            if not getattr(obj, schema.component_active_name(name), False):
                continue
            box = layout.box()
            header = box.row()
            label = name + ("  ·  behavior" if comp.get("hasSystem") else "")
            header.label(text=label)
            rm = header.operator("blenjs.remove_component", text="", icon="X", emboss=False)
            rm.component = name
            _draw_component(box.column(), comp, getattr(obj, schema.component_pg_name(name)), obj)


CLASSES = (
    BLENJS_UL_object_refs,
    BLENJS_MT_add_component,
    BLENJS_PT_inspector,
)
