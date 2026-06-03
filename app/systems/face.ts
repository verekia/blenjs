import type { Entity, Vec3 } from '@blenjs/core'
import { MODEL_YAW_OFFSET, TURN_LERP } from '../game/constants'

/**
 * Smoothly turn an entity to face its horizontal movement direction in the Z-up
 * world. `(dx, dy)` is the world-plane movement (magnitude ignored; any vertical
 * component is deliberately dropped so characters stay upright). Near-zero input is
 * a no-op, so a stopped entity keeps its last facing — "face the last movement when
 * idle". The yaw is written to Transform.rot[2]; the sync step in GameSystems drives
 * the mesh from it.
 */
export const faceMovement = (e: Entity, dx: number, dy: number, dt: number) => {
  if (dx * dx + dy * dy < 1e-8) return
  const rot = (e.components.Transform as { rot?: Vec3 } | undefined)?.rot
  if (!rot) return
  const diff = Math.atan2(dy, dx) + MODEL_YAW_OFFSET - rot[2]
  // Shortest-arc: wrap the delta into [-π, π] before damping toward it.
  rot[2] += Math.atan2(Math.sin(diff), Math.cos(diff)) * Math.min(1, dt * TURN_LERP)
}
