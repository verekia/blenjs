"""Cmd/Ctrl+S override (spec §6.7).

We bind save to the BlenJS export operator rather than relying on ``save_pre`` (which only
fires on real ``.blend`` saves — and BlenJS never saves a ``.blend``). The override is
CONDITIONAL: ``BLENJS_OT_export.poll()`` is true only when a BlenJS project is loaded, so in
any other file the keymap item is skipped and Blender's native save runs untouched.
"""

import bpy

_keymaps = []


def register() -> None:
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        return
    km = kc.keymaps.new(name="Window", space_type="EMPTY")
    for modifier in ({"ctrl": True}, {"oskey": True}):  # Ctrl+S (Win/Linux), Cmd+S (macOS)
        kmi = km.keymap_items.new("blenjs.export", type="S", value="PRESS", **modifier)
        _keymaps.append((km, kmi))


def unregister() -> None:
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (RuntimeError, ReferenceError):
            pass
    _keymaps.clear()
