import type { Entity, Vec3 } from '@blenjs/core'
import { GRAVITY, PLAYER_HALF } from '../game/constants'
import {
  aabbFromCenter,
  applyGroundedPushOut,
  colliderAABB,
  isAxisAlignedBox,
  overlap,
  resolveSphereVsCollider,
} from '../game/physics'
import type { GameContext } from '../game/types'
import { faceMovement } from './face'

// For sphere/capsule/rotated-box colliders the player is treated as a sphere (the inscribed
// radius of its AABB) and pushed out along the contact normal.
const PLAYER_RADIUS = Math.min(PLAYER_HALF[0], PLAYER_HALF[1], PLAYER_HALF[2])

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
  // hydrateGame seeds every entity's runtime to `{}`, so `!e.runtime` was never
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
    if (!isAxisAlignedBox(c)) continue // sphere/capsule/rotated boxes are handled by resolveShapes
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

// Push the player out of every sphere / capsule / rotated-box collider (the shapes the
// axis sweep skips), cancelling the velocity component going into each surface and grounding
// the player when it lands on top. Runs after the box sweep, so axis-aligned platforms win.
const resolveShapes = (pos: Vec3, rt: PlayerRuntime, ctx: GameContext) => {
  for (const c of ctx.colliders) {
    if (isAxisAlignedBox(c)) continue
    const hit = resolveSphereVsCollider(pos, PLAYER_RADIUS, c)
    if (!hit) continue
    // applyGroundedPushOut clamps any downward push (so the player is never shoved into the
    // floor box, which the per-axis sweep would then snap to its far edge) and cancels the
    // velocity going into the surface.
    const r = applyGroundedPushOut(hit, rt.vx, rt.vz)
    pos[0] += r.dx
    pos[1] += r.dy
    pos[2] += r.dz
    rt.vx = r.vx
    rt.vz = r.vz
    if (r.grounded) rt.grounded = true
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

  // Face the heading. rt.dir persists the last horizontal direction, so the player
  // keeps facing it while idle (movement is along X only — no depth component).
  faceMovement(e, rt.dir, 0, dt)

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

  // Sphere / capsule / rotated-box colliders (the shapes the axis sweep skips).
  resolveShapes(pos, rt, ctx)

  // Falling off the level is no longer a hardcoded Z threshold — an authored kill-volume
  // Trigger (action: 'lose', placed below the level in Blender) handles it. See systems/trigger.
}
