# BlenJS Blender add-on

Blender becomes the level editor for your R3F game. Drag a `game.yaml` into the
viewport to load every scene as a Blender Scene datablock, design with normal
Blender tools, and press **Cmd/Ctrl+S** to write canonical YAML back to the file
you loaded. No `.blend` is ever saved — Blender is a stateless view over the YAML.

## Requirements

- **Blender 4.1+** (the drag-and-drop `FileHandler` API was added in 4.1).
- The add-on reads `components.schema.json` (the codegen output) to build its UI.

## Install

**Option A — packaged zip (recommended):**

```bash
bun run codegen                       # writes generated/components.schema.json
python3 blender/tools/build_addon.py  # writes blender/dist/blenjs_addon.zip (schema bundled)
```

Then in Blender: **Edit ▸ Preferences ▸ Add-ons ▸ Install from Disk…** and pick
`blender/dist/blenjs_addon.zip`. Enable “BlenJS”.

**Option B — from the repo (dev):** point Blender's scripts path at this repo, or
symlink `blender/blenjs_addon` into your Blender `addons/` folder, then enable it.
When loaded from the repo, the add-on finds `generated/components.schema.json`
automatically (repo-relative).

> **Reinstalling? Restart Blender.** Blender does not re-import an add-on's Python
> modules on reinstall — the old code stays live in memory, so a fresh zip can look
> like it changed nothing. After **Install from Disk…** (or any code change), restart
> Blender to load the new code.

### Where the schema comes from

The add-on locates `components.schema.json` in this order:

1. the path set in **Add-on Preferences ▸ components.schema.json**
2. the `BLENJS_SCHEMA` environment variable
3. a copy bundled next to the add-on (what `build_addon.py` ships)
4. a repo-relative `generated/components.schema.json` (dev convenience)

Re-run `bun run codegen` and reload the add-on whenever you change the component
registry (`app/components.ts`).

## Workflow

1. **Load** — drag `game.yaml` onto the 3D viewport (or File ▸ Import ▸ BlenJS
   Game). Each YAML scene becomes a Blender Scene; switch scenes with Blender's
   native scene dropdown.
2. **Design** — move/rotate/scale objects normally (that *is* the `Transform`
   component). In Object Properties ▸ **BlenJS**, use **Add Component** (grouped by
   category) to attach typed components; entity-ref fields are drag-to-assign
   object pointers; array refs (e.g. `Patrol.waypoints`) use a list.

   > **Coordinates** — the game and Blender share one frame: **Z-up right-handed**
   > (X right, Y depth, Z up). Position and scale are *identical* on both sides and
   > pass through untouched; `game.yaml` is Z-up too. The one thing that still
   > differs is the Euler *order* for the same `'XYZ'` triple (three.js `Rx·Ry·Rz`
   > vs Blender `Rz·Ry·Rx`), so rotations are reconciled through matrices, not
   > copied verbatim (see `blenjs_addon/transform.py`). On the three.js side the
   > world is rendered Z-up by setting `Object3D.DEFAULT_UP` to +Z. (glTF is Y-up by
   > spec; lift imported models into the world with a +90° rotation about X.)
3. **Save** — **Cmd/Ctrl+S** writes canonical YAML back to the original path. Save
   is rebound to the BlenJS export operator (we don't rely on `save_pre`, which
   only fires for real `.blend` saves).

### Identity

Every object carries a stable `blenjs_uuid` custom property (generated lazily).
The YAML key *is* this UUID; references serialize to UUIDs and resolve back to
objects on load. Renaming an object never breaks references.

### The “Save changes?” dialog

Blender's own dirty flag may still prompt on quit/load. That's harmless — the real
save already happened on Cmd/Ctrl+S, and a discarded `.blend` costs nothing. Just
choose *Don't Save*.

## Tests

CI (no Blender required) — the canonicalizer is `bpy`-free and the datablock path
runs against a faithful fake `bpy`:

```bash
bun run test:roundtrip                          # load game.yaml -> save -> ZERO diff (+ normalization)
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
# ruamel.yaml must be importable by Blender's bundled python. Either install it
# into Blender, or point BLENJS_PYLIBS at a dir that has it:
BLENJS_PYLIBS=/path/with/ruamel \
  blender --background --factory-startup \
    --python blender/tests/test_in_blender.py
```

This drives the real add-on against the real `bpy`: byte-stable round-trip,
entity-ref (`Patrol.waypoints`) stability, and idempotent re-import.
