import type { Entity, Vec3 } from '@blenjs/core'
import { PICKUP_RADIUS } from '../game/constants'
import { distance } from '../game/physics'
import type { GameContext } from '../game/types'

type PickupData = { kind: string; value: number }

/**
 * Player-vs-pickup overlap: collecting removes the pickup and adds its value to
 * the score. Attached as the Pickup component's system (a "behavior").
 */
export const pickup = (e: Entity, data: PickupData, _dt: number, ctx: GameContext) => {
  const player = ctx.player
  if (!player) return
  const t = (e.components.Transform as { pos: Vec3 } | undefined)?.pos
  const pp = (player.components.Transform as { pos: Vec3 } | undefined)?.pos
  if (!t || !pp) return

  if (distance(t, pp) < PICKUP_RADIUS) {
    ctx.addScore(data.value)
    ctx.removeEntity(e.uuid)
  }
}
