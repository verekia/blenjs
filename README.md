# BlenJS

> A Blender-as-editor workflow for React Three Fiber games. Blender authors levels;
> YAML is the source of truth; logic lives in TypeScript; the game renders in an R3F
> **WebGPU** canvas inside Next.js.

Drop a `game.yaml` onto Blender, design a platformer, press **Cmd/Ctrl+S**, and
watch it reload as a playable WebGPU game.

BlenJS is **not a game engine**. It is an **editor + data pipeline** layered over
Blender, with R3F as the runtime.

## Principles (do not violate)

1. **YAML is the single source of truth.** `.blend` files are never saved or
   committed — Blender is a stateless view that loads YAML and writes YAML back.
2. **The TS component registry is the schema authority.** It generates
   `components.schema.json`, which Blender's Python reads to build its UI.
3. **Components and behaviors are one concept.** A component is typed data; a
   "behavior" is just a component the runtime has a registered _system_ for.
4. **Designed world vs. emergent world.** Authored things (platforms, coins,
   enemies, spawn, goal) come from YAML. Runtime-spawned things (bullets, score,
   win state, HUD) are code reading Zustand. Never author the emergent layer.
5. **Identity is by UUID, never by name.** Blender renames objects freely.
6. **The library layer stays extractable.** Dependencies point strictly outward
   from a runtime-agnostic core (see [Library organization](#library-organization)).

## Repository layout

```
blenjs/
  game.yaml                      # all scenes — THE source of truth (committed)
  generated/
    components.schema.json       # codegen output — committed (Blender reads it)
  packages/
    core/          # defineComponent + Zod registry. NO three/react/blender.
    codegen/       # registry -> components.schema.json (Node-only)
    runtime-three/ # YAML -> validated data -> entities + UUID refs (headless)
    runtime-r3f/   # React/R3F WebGPU layer: Level, ModelContainer, system ticker
  app/             # the Next.js platformer (application content)
    components.ts   #   the game vocabulary (the registry)
    systems/        #   playerController, patrol, pickup, shoot, goal
    game/           #   canvas, Level renderer, HUD, Zustand store
    pages/          #   Next.js (pages router, static export)
  blender/
    blenjs_addon/  # the Blender add-on (Python) — see blender/README.md
    tests/ tools/  # round-trip tests + addon packager
  scripts/         # codegen, watch (dev loop), runtime smoke test
```

## Quick start

Requires **[Bun](https://bun.sh)** (the package manager + runtime) and
**Python 3** with `ruamel.yaml` (for the Blender tooling/tests).

```bash
bun install            # installs the workspace; applies the Three/detect-gpu patches
bun run codegen        # registry -> generated/components.schema.json
bun run dev            # Next.js dev server (WebGPU canvas) at http://localhost:3000
```

Play with **← →** / **A D** to move, **Space / W** to jump, **F / J / click** to
shoot. Collect coins, shoot enemies, reach the magenta goal. **R** restarts.

For the live editing loop, run the watcher in a second terminal:

```bash
bun run watch          # regenerates schema on registry change; mirrors game.yaml -> app/public
```

Then editing `game.yaml` (or saving from Blender) hot-reloads the running game.

### Blender

See **[blender/README.md](blender/README.md)**. In short: `bun run codegen`, then
`python3 blender/tools/build_addon.py`, then install
`blender/dist/blenjs_addon.zip` (Blender 4.1+). Drag `game.yaml` into the viewport;
Cmd/Ctrl+S saves canonical YAML.

## How it fits together

```
app/components.ts (registry, Zod schemas + editor metadata)
        │  bun run codegen
        ▼
generated/components.schema.json ───────────────► Blender add-on builds typed UI
        │                                          (drag game.yaml in, edit, Cmd/Ctrl+S)
        │                                                       │
        ▼                                                       ▼ canonical YAML
game.yaml  ◄──────────────────────── the single source of truth ──────────────────
        │  fetch + parse (runtime-three)
        ▼
loadScene → Zod-validate each component → resolveRefs (UUID map)
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

`game.yaml` ships a playable platformer (`level1`): box platforms (`Collider`),
coins + a gem (`Pickup`), two patrolling enemies (`Enemy` + `Damageable` +
`Patrol` with waypoint refs), a `PlayerSpawn`, and a `Goal`. The player is spawned
in code at the spawn marker; bullets, score, ammo, and win/lose live only in
Zustand — never in YAML.

## Library organization

Publishing is **not** a current deliverable, but the packages are structured so
extraction is trivial. Dependency arrows point strictly **outward** from `core`:

| Package                 | Depends on                       | Imports three? | Imports react? |
| ----------------------- | -------------------------------- | -------------- | -------------- |
| `@blenjs/core`          | zod (peer)                       | no             | no             |
| `@blenjs/codegen`       | core                             | no             | no             |
| `@blenjs/runtime-three` | core (+ `yaml`)                  | no             | no             |
| `@blenjs/runtime-r3f`   | runtime-three, react, three, R3F | yes            | yes            |

The Blender add-on ships on its own channel (zip), versioned in lockstep with the
schema contract (`schemaVersion`). `game.yaml`, `app/components.ts`, and
`app/systems/` are application content — never a dependency, at most a starter.

## Commands

| Command                  | What it does                                                          |
| ------------------------ | --------------------------------------------------------------------- |
| `bun run codegen`        | registry → `generated/components.schema.json`                         |
| `bun run dev`            | Next.js dev server (WebGPU)                                           |
| `bun run build`          | codegen + Next.js static export to `app/out`                          |
| `bun run watch`          | dev loop glue: codegen on registry change + `game.yaml` → public sync |
| `bun run typecheck`      | `tsc --noEmit` across all workspaces                                  |
| `bun run gen:yaml`       | regenerate the canonical `game.yaml` from the level builder           |
| `bun run test:roundtrip` | the zero-diff YAML round-trip acceptance test                         |
| `bunx oxfmt . `          | format (matches the reference repo's config)                          |
| `bunx oxlint .`          | lint                                                                  |

## Verification

What is exercised headlessly in this repo (all green):

- **codegen** emits the enriched schema (vectors, enums, ints w/ bounds,
  entity-ref arrays, `hasSystem`).
- **YAML zero-diff round-trip** (`bun run test:roundtrip`): load → save = zero
  diff, idempotent, and messy input normalizes to canonical bytes.
- **Blender datablock round-trip** (`blender/tests/test_blender_roundtrip.py`):
  drives the real add-on data path through a fake `bpy` — load → datablocks →
  save is also zero-diff, with UUID refs resolving.
- **runtime** (`scripts/check-runtime.ts`): `loadScene` + `resolveRefs` on the
  real `game.yaml`, and validation errors name the component + entity.
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
