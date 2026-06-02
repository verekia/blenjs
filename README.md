# BlenJS

> A Blender-as-editor workflow for React Three Fiber games. Blender authors levels;
> JSON is the source of truth; logic lives in TypeScript; the game renders in an R3F
> **WebGPU** canvas inside Next.js.

Drop a `game.json` onto Blender, design a platformer, press **Cmd/Ctrl+S**, and
watch it reload as a playable WebGPU game.

BlenJS is **not a game engine**. It is an **editor + data pipeline** layered over
Blender, with R3F as the runtime.

## Principles (do not violate)

1. **JSON is the single source of truth.** `.blend` files are never saved or
   committed — Blender is a stateless view that loads JSON and writes JSON back.
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
  game.json                      # all scenes — THE source of truth (committed)
  generated/
    components.schema.json       # codegen output — committed (Blender reads it)
  packages/
    core/          # defineComponent + Zod registry. NO three/react/blender.
    codegen/       # registry -> components.schema.json (Node-only)
    runtime-three/ # JSON -> validated data -> entities + UUID refs (headless)
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
**Python 3** (standard library only — the Blender tooling/tests have no third-party
Python dependencies).

```bash
bun install            # installs the workspace; applies the Three/detect-gpu patches
bun run codegen        # registry -> generated/components.schema.json
bun run dev            # Next.js dev server (WebGPU canvas) at http://localhost:3000
```

Play with **← →** / **A D** to move, **Space / W** to jump, **F / J / click** to
shoot. Collect coins, shoot enemies, reach the magenta goal. **R** restarts.

The app imports `game.json` as a module, so editing it (or saving from Blender)
hot-reloads the running game through the dev server's Fast Refresh — no extra
process needed. To also regenerate the schema as you edit the component registry,
run the watcher in a second terminal:

```bash
bun run watch          # regenerates the schema on registry change
```

### Blender

See **[blender/README.md](blender/README.md)**. In short: `bun run codegen`, then
`python3 blender/tools/build_addon.py`, then install
`blender/dist/blenjs_addon.zip` (Blender 4.1+). Drag `game.json` into the viewport;
Cmd/Ctrl+S saves canonical JSON.

## How it fits together

```
app/components.ts (registry, Zod schemas + editor metadata)
        │  bun run codegen
        ▼
generated/components.schema.json ───────────────► Blender add-on builds typed UI
        │                                          (drag game.json in, edit, Cmd/Ctrl+S)
        │                                                       │
        ▼                                                       ▼ canonical JSON
game.json  ◄──────────────────────── the single source of truth ──────────────────
        │  imported as a module (bundled; HMR on save)
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

`game.json` ships a playable platformer (`level1`): box platforms (`Collider`),
coins + a gem (`Pickup`), two patrolling enemies (`Enemy` + `Damageable` +
`Patrol` with waypoint refs), a `PlayerSpawn`, and a `Goal`. The player is spawned
in code at the spawn marker; bullets, score, ammo, and win/lose live only in
Zustand — never in JSON.

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
schema contract (`schemaVersion`). `game.json`, `app/components.ts`, and
`app/systems/` are application content — never a dependency, at most a starter.

## Commands

| Command                  | What it does                                                   |
| ------------------------ | -------------------------------------------------------------- |
| `bun run codegen`        | registry → `generated/components.schema.json`                  |
| `bun run dev`            | Next.js dev server (WebGPU)                                    |
| `bun run build`          | codegen + Next.js static export to `app/out`                   |
| `bun run watch`          | regenerates `components.schema.json` when the registry changes |
| `bun run typecheck`      | `tsc --noEmit` across all workspaces                           |
| `bun run gen:json`       | regenerate the canonical `game.json` from the level builder    |
| `bun run test:roundtrip` | the zero-diff JSON round-trip acceptance test                  |
| `bunx oxfmt .`           | format (matches the reference repo's config)                   |
| `bunx oxlint .`          | lint                                                           |
| `bun run warden`         | repo config/version consistency check (`@verekia/warden`)      |
| `bun run all`            | format:check + lint + typecheck + warden — the CI gate         |

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
  real `game.json`, and validation errors name the component + entity.
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
