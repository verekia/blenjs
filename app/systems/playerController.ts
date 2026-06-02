import type { Entity, Vec3 } from '@blenjs/core'
import { GRAVITY, PLAYER_HALF, FALL_KILL_Z } from '../game/constants'
import { aabbFromCenter, colliderAABB, overlap } from '../game/physics'
import type { GameContext } from '../game/types'

type PlayerData = { moveSpeed: number; jumpForce: number }

export type PlayerRuntime = {
  vx: number
  vz: number
  grounded: boolean
  /** Facing direction (-1 left, +1 right) — used by the shoot system. */
  dir: number
  /** Fire cooldown timer (seconds). */
  fireCd: number
}

const getRuntime = (e: Entity): PlayerRuntime => {
  // hydrateFromJson seeds every entity's runtime to `{}`, so `!e.runtime` was never
  // true — the old guard left vx/vz/… undefined, and `rt.vz += GRAVITY*dt` turned
  // the player position into NaN (which propagated to the follow camera and blanked
  // the whole render). Seed each field defensively, like patrol/shoot already do.
  const rt = (e.runtime ??= {}) as Partial<PlayerRuntime>
  rt.vx ??= 0
  rt.vz ??= 0
  rt.grounded ??= false
  rt.dir ??= 1
  rt.fireCd ??= 0
  return e.runtime as unknown as PlayerRuntime
}

// Resolve the player AABB against all colliders along a single axis, after the
// position has been integrated on that axis. Standard per-axis platformer sweep.
// Axis 0 = X (horizontal), axis 2 = Z (vertical/up) — the world is Z-up.
const resolveAxis = (pos: Vec3, axis: 0 | 2, rt: PlayerRuntime, ctx: GameContext) => {
  for (const c of ctx.colliders) {
    const box = colliderAABB(c)
    if (!box) continue
    if (!overlap(aabbFromCenter(pos, PLAYER_HALF), box)) continue

    if (axis === 2) {
      if (rt.vz <= 0) {
        // Falling/standing: land on top of the platform.
        pos[2] = box.max[2] + PLAYER_HALF[2]
        rt.grounded = true
      } else {
        // Rising: bonk the underside.
        pos[2] = box.min[2] - PLAYER_HALF[2]
      }
      rt.vz = 0
    } else {
      if (rt.vx > 0) pos[0] = box.min[0] - PLAYER_HALF[0]
      else if (rt.vx < 0) pos[0] = box.max[0] + PLAYER_HALF[0]
      rt.vx = 0
    }
  }
}

export const playerController = (e: Entity, data: PlayerData, dt: number, ctx: GameContext) => {
  const t = e.components.Transform as { pos: Vec3 } | undefined
  if (!t?.pos) return
  const rt = getRuntime(e)
  const pos = t.pos

  const move = (ctx.input.right ? 1 : 0) - (ctx.input.left ? 1 : 0)
  rt.vx = move * data.moveSpeed
  if (move !== 0) rt.dir = move

  if (ctx.input.jump && rt.grounded) {
    rt.vz = data.jumpForce
    rt.grounded = false
  }
  rt.vz += GRAVITY * dt

  // Integrate + resolve one axis at a time so corners behave.
  pos[0] += rt.vx * dt
  resolveAxis(pos, 0, rt, ctx)

  rt.grounded = false
  pos[2] += rt.vz * dt
  resolveAxis(pos, 2, rt, ctx)

  if (pos[2] < FALL_KILL_Z) ctx.setLose()
}
