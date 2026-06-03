# BlenJS Blender add-on

Blender becomes the level editor for your R3F game. Drag a `.blen.json` project into the
viewport to load every scene as a Blender Scene datablock, design with normal Blender tools,
and press **Cmd/Ctrl+S** to write canonical JSON back to the file you loaded. No `.blend` is
ever saved — Blender is a stateless view over the JSON.

## Requirements

- **Blender 4.1+** (the drag-and-drop `FileHandler` API was added in 4.1).

## Install

Download `blenjs_addon.zip` (blenjs.com or the GitHub releases) and install it like any Blender
add-on: **Edit ▸ Preferences ▸ Add-ons ▸ Install from Disk…**, then enable “BlenJS”.

> Building it yourself: `python3 blender/tools/build_addon.py` writes
> `blender/dist/blenjs_addon.zip`. For add-on development, point Blender's scripts path at this
> repo or symlink `blender/blenjs_addon` into your `addons/` folder (restart Blender after
> reinstalling to pick up code changes).

## Project layout

A BlenJS project is a `<name>.blen.json` file. The add-on reads everything else relative to its
folder, so several projects can share one set of prefabs, schema, and assets:

```
platformer.blen.json               a project's scenes (shmup.blen.json, … can sit alongside)
generated/components.schema.json   the schema — bun run codegen (builds the editor UI)
generated/prefabs.json             the prefab manifest — bun run build:models
app/public/assets/<name>.glb       the built models — bun run build:models
prefabs/<name>.{json,blend}        prefab data + editable model source
```

Run `bun run codegen` and `bun run build:models` in your project, then load the `.blen.json`.
After changing components or models, re-run the relevant command and re-load it.

## Workflow

1. **Load** — drag `.blen.json` onto the 3D viewport (or File ▸ Import ▸ BlenJS
   Game). Each scene becomes a Blender Scene; switch scenes with Blender's
   native scene dropdown.
2. **Design** — move/rotate/scale objects normally (that *is* the `Transform`
   component). In Object Properties ▸ **BlenJS**, use **Add Component** (grouped by
   category) to attach typed components; entity-ref fields are drag-to-assign
   object pointers; array refs (e.g. `Patrol.waypoints`) use a list.

   > **Coordinates** — the game and Blender share one frame: **Z-up right-handed**
   > (X right, Y depth, Z up). Position and scale are *identical* on both sides and
   > pass through untouched; `.blen.json` is Z-up too. The one thing that still
   > differs is the Euler *order* for the same `'XYZ'` triple (three.js `Rx·Ry·Rz`
   > vs Blender `Rz·Ry·Rx`), so rotations are reconciled through matrices, not
   > copied verbatim (see `blenjs_addon/transform.py`). On the three.js side the
   > world is rendered Z-up by setting `Object3D.DEFAULT_UP` to +Z. Linked prefab
   > `.blend` sources are native Z-up, so the viewport applies no rotation correction.
3. **Save** — **Cmd/Ctrl+S** writes canonical JSON back to the original path. Save
   is rebound to the BlenJS export operator (we don't rely on `save_pre`, which
   only fires for real `.blend` saves).

### Prefabs & models

Entities that reference a **prefab** (`"prefab": "coin"`) or carry a **`Model`** component
are visualized with their real geometry by **library-linking** the editable source
`prefabs/<src>.blend` (Blender's "Link" feature) and showing it as a **collection
instance**: the geometry lives in the external `.blend` and is only *referenced*, never
copied into the scene, so the viewport shows actual coins/enemies/etc. instead of
placeholder cubes. One linked holder collection (`BLENJS_SRC_<name>`) is shared by every
instance; because the source is native Z-up, no rotation correction is applied. `Model.src`
is a **bare name** (`"coin"` → `prefabs/coin.blend`) — the built `.glb` is only the web
runtime's artifact and is never referenced here.

- Editing a `Model`'s **`src`** in the BlenJS panel **swaps the model live**: the new
  `.blend` is linked and re-instanced immediately.
- A prefab instance shows its **resolved** values (prefab defaults + the instance's
  overrides) in the BlenJS panel, with a `Prefab: <name>` line. Move/rotate/scale it or
  edit a field, then Cmd/Ctrl+S — only what **differs from the prefab** is written back
  (Transform is always per-instance). The geometry's source of truth is
  `prefabs/<name>.blend`, edited directly — the linked viewport is WYSIWYG with it on the
  next load (no `build:models` needed for visualization; that only refreshes the runtime
  `.glb`).
- If a `.blend` source (or the linking API, under headless tests) is unavailable, instances
  fall back to a placeholder empty but still round-trip their data correctly.

### Identity

Every object carries a stable `blenjs_uuid` custom property (generated lazily).
The JSON key *is* this UUID; references serialize to UUIDs and resolve back to
objects on load. Renaming an object never breaks references.

### The “Save changes?” dialog

Blender's own dirty flag may still prompt on quit/load. That's harmless — the real
save already happened on Cmd/Ctrl+S, and a discarded `.blend` costs nothing. Just
choose *Don't Save*.

## Tests

CI (no Blender required) — the canonicalizer is `bpy`-free and the datablock path
runs against a faithful fake `bpy`:

```bash
bun run test:roundtrip                          # load .blen.json -> save -> ZERO diff (+ normalization)
python3 blender/tests/test_blender_roundtrip.py # datablock round-trip via a fake bpy (load->datablocks->save = 0 diff)
python3 blender/tests/test_transform.py         # Z-up Euler-order conversion: conventions + exact round-trip
```

> The fake models Blender's two property namespaces separately: ID-properties
> (`obj["k"]` / `obj.get("k")`) and registered RNA props (`obj.k`). They never see
> each other in real Blender, so `blenjs_uuid` identity must use **one** of them
> consistently (we use ID-properties). Mixing the two — writing `obj.blenjs_uuid =`
> but reading `obj.get("blenjs_uuid")` — makes `ensure_uuid` re-mint a UUID on every
> call, which corrupts entity-refs. This test catches that.

Authoritative (inside real Blender, headless):

```bash
# Parsing/writing uses the stdlib `json` module, so there is nothing to install
# into Blender's bundled python — just run it:
blender --background --factory-startup \
  --python blender/tests/test_in_blender.py
```

This drives the real add-on against the real `bpy`: byte-stable round-trip,
entity-ref (`Patrol.waypoints`) stability, and idempotent re-import.
