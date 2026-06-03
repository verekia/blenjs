# BlenJS — authoring-experience roadmap

Analysis of what the Blender + JSON + React pipeline supports today and what is
missing for a feature-rich, comfortable **author-in-Blender** experience. Audience:
developers who want Blender to carry the art / game-design / content load and write
as little of that content in code as possible.

## The central gap

Exactly **one** piece of Blender's native scene data is mapped into the game today:
the object **`Transform`**. Everything else Blender is actually _for_ — lighting,
cameras, materials, modeled geometry, parenting, animation — is either **discarded on
export or hardcoded in React**. The component registry (the schema authority that
drives Blender's UI) is excellent and extensible, but so far it has only been used to
express _gameplay_ data, not Blender's _art_ outputs.

Two proven extension patterns exist in the codebase:

- **(A) Native-datablock mapping** — how `Transform` already works: on import create
  the real Blender datablock (gizmos/manipulation for free), on export read it back
  into a component. The path for **lights, cameras, materials, animation, meshes**.
- **(B) Pure custom components** — the registry pattern (`defineComponent`). For things
  with no native datablock: **scene settings, triggers, spawners, event wiring**.

> Lights, Camera, Material colors, and Trigger event-wiring are implemented. `Light`/`Camera`
> are authored as components **and** mapped to **real Blender datablocks** (a Sun lamp, a Camera
> object, the World) on import via pattern **(A)** — so the viewport frames and lights like the
> game (verified headless in Blender 5.1). The component PropertyGroups stay the export source of
> truth, so the JSON round-trip is unchanged.

---

## Status legend

- [x] done in this pass
- [~] partially done
- [ ] not started
- 🔥 silently misleads authors today — fix early

## Tier 1 — capture what Blender is _for_ (art outputs)

- [x] **Lights** (`Light` component: `ambient` | `directional`, color, intensity).
      Runtime renders `ambientLight` / `directionalLight` (directional direction from
      `Transform.rot`); old hardcoded lights are a fallback used only when a scene authors
      none. **Blender import builds a real Sun lamp** (directional) and drives the **World**
      (ambient), so the viewport lights like the game.
- [x] **Camera** (`Camera` component: projection, zoom, fov, near, far; position from the
      entity Transform). Runtime configures the `<Canvas>` from it (else the old ortho rig).
      **Blender import builds a real Camera object** set as the scene's active camera (Numpad 0
      frames the game; looks +Y via `rot=[π/2,0,0]`).
- [x] **Material colors** (`Material` component: color, opacity, unlit). Primitive blockout
      (platforms, goal, …) reads it instead of the hex literals baked into `Level.tsx`; colours
      are sRGB. Models keep their own glTF materials.
- [ ] **In-scene level geometry.** A mesh modeled directly in a level is reduced to a
      unit cube — only prefab `.blend` geometry renders. Add a build step that bakes a
      scene's non-prefab meshes to `level.glb` (committed artifact; JSON stays
      authoritative for entities) so environment art can be modeled in the level file.
- [ ] **Animation.** Even if clips ride along in a prefab `.glb`, nothing plays them —
      no mixer, no way to pick a clip. Add an `Animator` component + runtime
      `useAnimations`, and export animations in `build_assets.py`.
- [x] **Lights/Camera as native datablocks (pattern A).** Import builds real Sun / Camera /
      World datablocks from the components (best-effort; falls back to an empty under the
      headless fake-bpy). Trigger volumes display as cube-empties. _Follow-up:_ read the native
      datablock back on **export** (edit the raw Blender lamp/camera and have it round-trip), and
      author lights/cameras from real Blender `LIGHT`/`CAMERA` objects rather than empties+components.
- [ ] **Material from the Blender object** (read viewport/Principled base color on
      export) so the swatch you set in Blender _is_ the game color, no separate field.

## Tier 2 — make game _design_ authorable as data (no code)

- [ ] **Scene / World settings.** A scene is just `{entities}` today; per-level
      `gravity`, `background`, `ambient`, `fog`, `skybox`, `music`, `name`, `order`,
      `nextScene` live in `constants.ts` / `Game.tsx`. Add a scene-level `settings`
      block + a Blender Scene/World panel. Cheap, high design payoff.
- [x] **Triggers + event wiring.** `Trigger` component (`on` enter/exit, `action`
      win/lose/remove, `targets` entityRef array, `once`) + runtime system: a non-solid volume
      (entity scale = full extents) that fires on player crossing. `remove` deletes its
      `targets` — the entityRef _wiring_. Used in the game: an authored **kill volume**
      (`action: lose`) replaced the hardcoded `FALL_KILL_Z`, and a **rune** removes target
      enemies. Authored fully in Blender (the `targets` list is the same drag-to-assign UI as
      `Patrol.waypoints`; volumes show as cube-empties). _Follow-up:_ richer actions
      (enable/spawn/toggle), per-action target lists, non-player triggers.
- [ ] **Spawners.** A `Spawner` (prefab ref + rate/count/max) makes waves/emitters
      authorable instead of code-only like bullets.
- [ ] 🔥 **Collider shape / rotation honesty.** `Collider` advertises
      `box | sphere | capsule`, but physics only does an axis-aligned box and never
      reads `shape` or `rot` (`colliderAABB` uses `Transform.scale` alone). Implement
      sphere/capsule + slopes (or adopt a physics engine with collision layers), or
      constrain the enum and warn.

## Tier 3 — editor comfort

- [ ] **Placement from Blender.** No "Add → Coin". Mark prefabs as Asset Browser assets
      (drag-drop to stamp) and/or an `Add Entity from Prefab` operator.
- [ ] **In-Blender validation.** Zod runs only in the browser, so invalid data (missing
      required `Collider.shape`, a `Patrol` with < 2 waypoints, a ref to a deleted
      object) is only caught after alt-tabbing. A live panel reading the same schema
      should flag it at author time.
- [~] **Visualizers/gizmos.** Trigger volumes now show as cube-empties, and lights/cameras as
  native gizmos. Still missing: waypoint paths drawn as lines between `Patrol.waypoints`.
- [ ] **Explicit start scene & level order.** Order comes from `Object.keys(scenes)`
      today; make it data.
- [ ] **Prefab-data editing in Blender.** Prefab _defaults_ live in hand-edited
      `prefabs/*.json`; the `.blend` is geometry only.

## Correctness traps to close early

- [ ] 🔥 **Parenting breaks export.** Export reads each object's **local** transform
      (location / rotation / scale) and records **no parent**, so a parented object's
      local transform is written as if it were world. Designers parent things
      instinctively. Support hierarchy (a `parent` field + nested transforms) or
      flatten-to-world on export with a warning.
- [ ] 🔥 **Collider shape/rotation ignored** (see Tier 2).

## Repo hygiene found along the way

- [x] **`gen_game_json.py` was stale** — it had an empty `level2` while the committed
      `platformer.blen.json` shipped a full one, so `bun run gen:json` would have wiped
      `level2`. Ported `level2` back into the generator (now the true source of truth).
- [x] **In-Blender round-trip was failing (pre-existing).** `level2` reused `level1`'s object
      names (`spawn`, `goal`, `coin_01`, …); Blender names are globally unique across the file,
      so the second scene imported as `spawn.001`, breaking the round-trip. Namespaced `level2`
      (`l2_…`). The fake-bpy test couldn't catch it (no global name table); `test_in_blender.py`
      needs real Blender and isn't in CI. _Follow-up:_ store a logical name separate from
      `obj.name`, or accept Blender's uniquified names (per principle #5, identity is UUID).
- [x] **Redundant `Patrol.speed` override** on `level2 enemy_02` (equalled the prefab default)
      made the committed file disagree with Blender's diff-based export — dropped it.

## Suggested sequence

Done so far: Lights, Camera, Material colors (+ real Blender datablocks), Triggers + event
wiring. Next: Scene/World settings → Material-from-object → Spawners → in-scene mesh baking →
Animation. Close the parenting + collider traps alongside — they actively mislead authors today.
