import type { Entity, Vec3 } from '@blenjs/core'

export type Input = {
  left: boolean
  right: boolean
  jump: boolean
  shoot: boolean
}

/** A runtime-spawned bullet — emergent state, never authored in JSON. */
export type Bullet = {
  id: number
  pos: Vec3
  vel: Vec3
  ttl: number
}

/**
 * The per-frame context passed to every system. Built by the runtime from the
 * Zustand store. Systems are pure functions of `(entity, data, dt, ctx)` — all
 * world access goes through here, so the logic stays headless-testable.
 */
export type GameContext = {
  dt: number
  elapsed: number
  /** All live entities (designed + the runtime-spawned player). */
  entities: Entity[]
  getEntity: (uuid: string) => Entity | undefined
  /** Entities carrying a Collider — the platformer's solid geometry. */
  colliders: Entity[]
  /** The runtime player entity (carries the Player component), if spawned. */
  player: Entity | undefined
  input: Input
  /** Fire a bullet from `pos` travelling in `dirX` (-1/+1). Returns false if out of ammo. */
  spawnBullet: (pos: Vec3, dirX: number) => boolean
  addScore: (n: number) => void
  removeEntity: (uuid: string) => void
  setWin: () => void
  setLose: () => void
}
