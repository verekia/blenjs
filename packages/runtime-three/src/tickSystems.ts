import type { Entity, Registry } from '@blenjs/core'

/**
 * Run every behavior component's system once for the frame. Pure logic — no React,
 * no three. The R3F layer wraps this in a single `useFrame`; a headless test could
 * call it in a plain loop.
 *
 * Components are iterated in registry order (outer), entities inner, so system
 * execution order is deterministic and authorable (e.g. the player moves before
 * pickup/goal overlap checks run).
 */
export type TickContext = {
  entities: Entity[]
  [key: string]: unknown
}

export const tickSystems = (registry: Registry, ctx: TickContext, dt: number): void => {
  for (const def of registry.components) {
    if (!def.system) continue
    for (const entity of ctx.entities) {
      const data = entity.components[def.name]
      if (data) def.system(entity, data, dt, ctx)
    }
  }
}
