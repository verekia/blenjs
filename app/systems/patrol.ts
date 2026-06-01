import type { Entity, Vec3 } from '@blenjs/core'
import type { GameContext } from '../game/types'

type PatrolData = { speed: number; waypoints: string[]; loop: boolean }

type PatrolRuntime = { patrolIdx: number; patrolDir: number }

/**
 * Moves an entity between its waypoint entities, turning at the ends. Waypoints
 * are entity refs (UUIDs) resolved through the context — the same UUID identity
 * the Blender side uses. With `loop` the path cycles; otherwise it ping-pongs.
 */
export const patrol = (e: Entity, data: PatrolData, dt: number, ctx: GameContext) => {
  const t = e.components.Transform as { pos: Vec3 } | undefined
  if (!t?.pos || data.waypoints.length < 2) return

  const rt = (e.runtime ??= {}) as Partial<PatrolRuntime>
  rt.patrolIdx ??= 0
  rt.patrolDir ??= 1

  const target = ctx.getEntity(data.waypoints[rt.patrolIdx])
  const tp = (target?.components.Transform as { pos: Vec3 } | undefined)?.pos
  if (!tp) return

  const pos = t.pos
  const dx = tp[0] - pos[0]
  const dy = tp[1] - pos[1]
  const dz = tp[2] - pos[2]
  const dist = Math.hypot(dx, dy, dz)
  const step = data.speed * dt

  if (dist <= step || dist < 1e-5) {
    pos[0] = tp[0]
    pos[1] = tp[1]
    pos[2] = tp[2]
    let next = rt.patrolIdx + rt.patrolDir
    if (next >= data.waypoints.length) {
      if (data.loop) next = 0
      else {
        rt.patrolDir = -1
        next = rt.patrolIdx - 1
      }
    } else if (next < 0) {
      if (data.loop) next = data.waypoints.length - 1
      else {
        rt.patrolDir = 1
        next = rt.patrolIdx + 1
      }
    }
    rt.patrolIdx = Math.max(0, Math.min(data.waypoints.length - 1, next))
  } else {
    pos[0] += (dx / dist) * step
    pos[1] += (dy / dist) * step
    pos[2] += (dz / dist) * step
  }
}
