# BlenJS

> A Blender-as-editor workflow for React Three Fiber games. Blender authors levels;
> JSON is the source of truth; logic lives in TypeScript; the game renders in an R3F
> **WebGPU** canvas inside Next.js.

Drop a `platformer.blen.json` onto Blender, design a platformer, press **Cmd/Ctrl+S**, and
watch it reload as a playable WebGPU game.

BlenJS is **not a game engine**. It is an **editor + data pipeline** layered over
Blender, with R3F as the runtime.

## Principles (do not violate)

1. **JSON is the single source of truth** for _levels_. Level/scene `.blend` files are
   never saved or committed — Blender is a stateless view that loads JSON and writes JSON
   back. Reusable **prefab/model art** is the one deliberate exception: `prefabs/*.blend`
   are committed sources, built into committed `*.glb` (see [Prefabs & models](#prefabs--models)).
2. **The TS component registry is the schema authority.** It generates
   `components.schema.json`, which Blender's Python reads to build its UI.
3. **Components and behaviors are one concept.** A component is typed data; a
   "behavior" is just a component the runtime has a registered _system_ for.
4. **Designed world vs. emergent world.** Authored things (platforms, coins,
   enemies, spawn, goal) come from JSON. Runtime-spawned things (bullets, score,
   win state, HUD) are code reading Zustand. Never author the emergent layer.
5. **Identity is by UUID, never by name.** Blender renames objects freely.
6. **The library layer stays extractable.** Dependencies point strictly outward
   from a runtime-agnostic core (see [Library organization](#library-organization)).

## Repository layout

```
blenjs/
  platformer.blen.json           # a project (scenes) — source of truth; a repo can hold several *.blen.json
  prefabs/                       # reusable prefab/model art (committed)
    coin.json coin.blend         #   data (components + defaults) + editable model source
    …                            #   pickup, enemy, player
  generated/
    components.schema.json       # codegen output — committed (Blender reads it)
    prefabs.json                 # aggregated prefab manifest — committed (runtime + Blender read it)
  packages/
    core/          # defineComponent + Zod registry. NO three/react/blender.
    codegen/       # registry -> components.schema.json (Node-only)
    runtime-three/ # JSON -> resolvePrefabs -> validated data -> entities + UUID refs (headless)
    runtime-r3f/   # React/R3F WebGPU layer: Level, ModelContainer, system ticker
  app/             # the Next.js platformer (application content)
    components.ts   #   the game vocabulary (the registry, incl. the Model component)
    systems/        #   playerController, patrol, pickup, shoot, goal
    game/           #   canvas, Level renderer (glTF via useGLTF), HUD, Zustand store
    public/assets/  #   built *.glb (committed; served at /assets, copied to the export)
    pages/          #   Next.js (pages router, static export)
  blender/
    blenjs_addon/  # the Blender add-on (Python) — see blender/README.md
    tests/ tools/  # round-trip tests + addon/asset packagers (build_assets.py)
  scripts/         # codegen, watch (dev loop), runtime smoke test
```

## Quick start

Requires **[Bun](https://bun.sh)** (the package manager + runtime) and
**Python 3** (standard library only — the Blender tooling/tests have no third-party
Python dependencies).

```bash
bun install            # installs the workspace; applies the Three/detect-gpu patches
bun run codegen        # registry -> generated/components.schema.json
bun run dev            # Next.js dev server (WebGPU canvas) at http://localhost:3000
```

Play with **← →** / **A D** to move, **Space / W** to jump, **F / J / click** to
shoot. Collect coins, shoot enemies, reach the magenta goal. **R** restarts.

The app imports `platformer.blen.json` as a module, so editing it (or saving from Blender)
hot-reloads the running game through the dev server's Fast Refresh — no extra
process needed. To also regenerate the schema as you edit the component registry,
run the watcher in a second terminal:

```bash
bun run watch          # regenerates the schema on registry change
```

### Blender

See **[blender/README.md](blender/README.md)**. Install `blenjs_addon.zip` like any Blender
add-on (Blender 4.1+), run `bun run codegen` and `bun run build:models` in your project, then
drag `platformer.blen.json` into the viewport and Cmd/Ctrl+S to save.

## How it fits together

```
app/components.ts (registry, Zod schemas + editor metadata)
        │  bun run codegen
        ▼
generated/components.schema.json ───────────────► Blender add-on builds typed UI
        │                                          (drag platformer.blen.json in, edit, Cmd/Ctrl+S)
        │                                                       │
        ▼                                                       ▼ canonical JSON
platformer.blen.json  ◄──────────────────────── the single source of truth ──────────────────
        │  imported as a module (bundled; HMR on save)
        ▼
resolvePrefabs (merge prefab defaults + overrides) → loadScene (Zod) → resolveRefs (UUID map)
        │      ▲ generated/prefabs.json + app/public/assets/*.glb  ◄── bun run build:models (prefabs/*.blend)
        │
        ▼
Zustand store (designed entities + runtime player) ── systems tick in one useFrame
        │                                              (runtime-three.tickSystems)
        ▼
R3F WebGPU canvas renders the Level; bullets/score/HUD are the emergent layer
```

The same Zod schemas validate on load, so a malformed value reports _which
component on which entity_ failed.

## The example game

`platformer.blen.json` ships a playable platformer (`level1`): box platforms (`Collider`,
parametric blockout — no model), `coin`/`pickup`/`enemy` **prefab instances** (gold
coins, a cyan gem, two patrolling enemies), a `PlayerSpawn`, and a `Goal`. The player
is spawned in code at the spawn marker from the `player` prefab; bullets, score, ammo,
and win/lose live only in Zustand — never in JSON.

## Prefabs & models

A **prefab** is a reusable, model-backed entity authored once and stamped many times.
It is two committed files under `prefabs/`:

- `coin.json` — the **data**: a `components` map (defaults), including a `Model`
  component that names the model (`{"Model": {"src": "coin"}}`).
- `coin.blend` — the **editable model source**.

In **Blender**, a `Model` is visualized by _library-linking_ `prefabs/<src>.blend` directly
(shown as a collection instance — geometry referenced, never copied into the scene), so
authoring is WYSIWYG with the `.blend` and only ever names the model. For the **web
runtime**, `bun run build:models` runs Blender headless to (1) export each `prefabs/*.blend`
→ `app/public/assets/<name>.glb` (modifiers applied, kept **Z-up** so it drops into the
game's Z-up world with no rotation) and (2) aggregate `prefabs/*.json` →
`generated/prefabs.json`. Both outputs are committed, so the web build never needs Blender.
Re-run it whenever a prefab's `.blend` or `.json` changes (`.glb` is purely the runtime
artifact).

A `.blen.json` entity references a prefab with the reserved `prefab` key and overrides
**Transform + individual component fields** (`Model` itself is the single-use primitive —
an entity may carry a bare `Model` with no prefab):

```jsonc
"5f6102bd": { "name": "coin_01", "prefab": "coin",
              "Transform": { "pos": [5, 0, 3] },  // placement; scale inherited
              "Pickup": { "value": 50 } }         // field override; kind inherited
```

Prefab + overrides are merged at load (`@blenjs/runtime-three`'s `resolvePrefabs`,
before Zod) so editing a prefab updates every instance. In **Blender** the same merge
drives visualization — instances show the linked `.blend` geometry — and saving (Cmd/Ctrl+S)
writes each instance back **sparsely**: only the fields that differ from the prefab.

## Library organization

Publishing is **not** a current deliverable, but the packages are structured so
extraction is trivial. Dependency arrows point strictly **outward** from `core`:

| Package                 | Depends on                       | Imports three? | Imports react? |
| ----------------------- | -------------------------------- | -------------- | -------------- |
| `@blenjs/core`          | zod (peer)                       | no             | no             |
| `@blenjs/codegen`       | core                             | no             | no             |
| `@blenjs/runtime-three` | core (stdlib JSON)               | no             | no             |
| `@blenjs/runtime-r3f`   | runtime-three, react, three, R3F | yes            | yes            |

The Blender add-on ships on its own channel (zip), versioned in lockstep with the
schema contract (`schemaVersion`). `platformer.blen.json`, `app/components.ts`, and
`app/systems/` are application content — never a dependency, at most a starter.

## Commands

| Command                  | What it does                                                                               |
| ------------------------ | ------------------------------------------------------------------------------------------ |
| `bun run codegen`        | registry → `generated/components.schema.json`                                              |
| `bun run build:models`   | Blender headless: `prefabs/*.blend` → `app/public/assets/*.glb` + `generated/prefabs.json` |
| `bun run dev`            | Next.js dev server (WebGPU)                                                                |
| `bun run build`          | codegen + Next.js static export to `app/out`                                               |
| `bun run watch`          | regenerates `components.schema.json` when the registry changes                             |
| `bun run typecheck`      | `tsc --noEmit` across all workspaces                                                       |
| `bun run gen:json`       | regenerate the canonical `platformer.blen.json` from the level builder                     |
| `bun run test:roundtrip` | the zero-diff JSON round-trip acceptance test                                              |
| `bunx oxfmt .`           | format (matches the reference repo's config)                                               |
| `bunx oxlint .`          | lint                                                                                       |
| `bun run warden`         | repo config/version consistency check (`@verekia/warden`)                                  |
| `bun run all`            | format:check + lint + typecheck + warden — the CI gate                                     |

## Verification

What is exercised headlessly in this repo (all green):

- **codegen** emits the enriched schema (vectors, enums, ints w/ bounds,
  entity-ref arrays, `hasSystem`).
- **JSON zero-diff round-trip** (`bun run test:roundtrip`): load → save = zero
  diff, idempotent, and messy input normalizes to canonical bytes.
- **Blender datablock round-trip** (`blender/tests/test_blender_roundtrip.py`):
  drives the real add-on data path through a fake `bpy` — load → datablocks →
  save is also zero-diff, with UUID refs resolving.
- **runtime** (`scripts/check-runtime.ts`): `loadScene` + `resolveRefs` on the
  real `platformer.blen.json`, and validation errors name the component + entity.
- **`tsc --noEmit`** clean across all packages + app; **`next build`** static
  export succeeds; **oxfmt/oxlint** clean.

What requires a real environment to verify: live WebGPU rendering/gameplay (needs
a GPU + browser) and the interactive Blender UI (operators, keymap, drag-drop). The
data contracts both sides depend on are the parts proven above.

## Toolchain

Bun, React 19 (+ React Compiler), Next.js 16 (pages router, static export),
React Three Fiber v10 (canary) + Drei v11 (alpha) on the Three.js **WebGPU**
renderer (`three@0.182.0` with the required Bun patches), Zustand 5, Zod 4. These
versions and patches mirror the reference `r3f-gamedev` repo exactly.

Linting/formatting is **oxlint + oxfmt only** (no Prettier, no ESLint).
**[`@verekia/warden`](https://www.npmjs.com/package/@verekia/warden)** enforces
config + pinned-version consistency; `bun run all` (run by CI in
`.github/workflows/ci.yml`) gates format, lint, typecheck, and warden.
