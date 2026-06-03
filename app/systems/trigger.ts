import type { Entity, Vec3 } from '@blenjs/core'
import { PLAYER_HALF } from '../game/constants'
import { aabbFromCenter, colliderAABB, overlap } from '../game/physics'
import type { GameContext } from '../game/types'

type TriggerData = {
  on: 'enter' | 'exit'
  action: 'win' | 'lose' | 'remove'
  targets: string[]
  once: boolean
}

type TriggerRuntime = { triggerInside: boolean; triggerFired: boolean }

/**
 * Data-authored event wiring (the "design in Blender, not code" multiplier). A
 * `Trigger` is a non-solid volume — the entity Transform's pos + scale as full
 * extents, exactly like a Collider's box but it never blocks movement — that fires an
 * action when the player crosses into (or out of) it:
 *
 *   - `win` / `lose` end the level (global; targets ignored).
 *   - `remove` deletes the referenced `targets` (entity UUIDs), or the trigger itself
 *     if none are set. This is the entity-ref *wiring*: one entity's event affects
 *     others (a switch opening a gate, a rune clearing enemies, …).
 *
 * Everything is authored in Blender — the trigger box is the object's scale, and
 * `targets` is the same drag-to-assign object list as `Patrol.waypoints`. No bespoke
 * code per interaction. Attached as the `Trigger` component's system.
 */
export const trigger = (e: Entity, data: TriggerData, _dt: number, ctx: GameContext) => {
  const player = ctx.player
  if (!player) return
  const box = colliderAABB(e)
  const pp = (player.components.Transform as { pos: Vec3 } | undefined)?.pos
  if (!box || !pp) return

  const rt = (e.runtime ??= {}) as Partial<TriggerRuntime>
  rt.triggerInside ??= false
  rt.triggerFired ??= false

  const inside = overlap(aabbFromCenter(pp, PLAYER_HALF), box)
  // Edge-triggered: fire on the frame the player crosses the boundary, not every frame within.
  const crossed = data.on === 'exit' ? rt.triggerInside && !inside : !rt.triggerInside && inside
  rt.triggerInside = inside
  if (!crossed || (data.once && rt.triggerFired)) return
  rt.triggerFired = true

  if (data.action === 'win') ctx.setWin()
  else if (data.action === 'lose') ctx.setLose()
  else {
    const targets = data.targets.length > 0 ? data.targets : [e.uuid]
    for (const id of targets) ctx.removeEntity(id)
  }
}
