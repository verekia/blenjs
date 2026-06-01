import { useFrame } from '@react-three/fiber/webgpu'
import { Fragment, useRef, type ReactNode } from 'react'
import type { Object3D } from 'three'
import type { Entity, Registry } from '@blenjs/core'
import { tickSystems, type TickContext } from '@blenjs/runtime-three'

/**
 * @blenjs/runtime-r3f — the React/R3F view layer (outermost package).
 *
 * Imports follow the reference repo exactly: R3F comes from the WebGPU entry
 * `@react-three/fiber/webgpu`. This package is renderer-specific; the headless
 * data + system logic lives one layer in (`@blenjs/runtime-three`).
 */

export type MakeContext = (dt: number, elapsed: number) => TickContext

/**
 * Ticks every behavior component's system once per frame inside a single
 * `useFrame`. The app supplies `makeContext`, which reads its store and builds the
 * per-frame context (input, spawn helpers, the entity list, …).
 */
export const SystemsRunner = ({ registry, makeContext }: { registry: Registry; makeContext: MakeContext }) => {
  const elapsed = useRef(0)
  useFrame((_, dt) => {
    elapsed.current += dt
    const ctx = makeContext(dt, elapsed.current)
    tickSystems(registry, ctx, dt)
  })
  return null
}

/**
 * Syncs each entity's logical `Transform` onto its captured Three.js object every
 * frame (the architecture skill's "ThreeSystem"). Only entities that captured a
 * `three` ref via `ModelContainer` are touched; static meshes set their transform
 * once via props and are skipped.
 */
export const ThreeSyncSystem = ({ entities }: { entities: Entity[] }) => {
  useFrame(() => {
    for (const e of entities) {
      const o = e.three as Object3D | undefined
      if (!o) continue
      const t = e.components.Transform as { pos?: number[]; rot?: number[] } | undefined
      if (t?.pos) o.position.set(t.pos[0], t.pos[1], t.pos[2])
      if (t?.rot) o.rotation.set(t.rot[0], t.rot[1], t.rot[2])
    }
  })
  return null
}

/**
 * Captures an entity's Three.js Object3D so systems can manipulate it directly
 * (reference repo's ModelContainer pattern). Smart `*Entity` wrappers use this;
 * dumb `*Model` components stay renderer-only.
 */
export const ModelContainer = ({ entity, children }: { entity: Entity; children: ReactNode }) => (
  <group
    ref={ref => {
      if (!ref) return
      entity.three = ref
      return () => {
        entity.three = undefined
      }
    }}
  >
    {children}
  </group>
)

export type EntityRenderer = (entity: Entity) => ReactNode

/**
 * Maps a list of entities to R3F objects via an app-supplied renderer. Keyed by
 * UUID so add/remove re-renders are stable (identity is never by name).
 */
export const Level = ({ entities, renderEntity }: { entities: Entity[]; renderEntity: EntityRenderer }) => (
  <>
    {entities.map(e => (
      <Fragment key={e.uuid}>{renderEntity(e)}</Fragment>
    ))}
  </>
)
