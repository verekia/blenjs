import type { Vec3 } from '@blenjs/core'
import { GOAL_RADIUS } from '../game/constants'
import { distance } from '../game/physics'
import type { GameContext } from '../game/types'

/**
 * Goal is a pure-data marker component (spec §3 lists it as pure-data). Win
 * detection runs as a runtime system: when the player overlaps any Goal entity,
 * trigger the win state.
 */
export const goalStep = (_dt: number, ctx: GameContext) => {
  const player = ctx.player
  if (!player) return
  const pp = (player.components.Transform as { pos: Vec3 } | undefined)?.pos
  if (!pp) return

  for (const e of ctx.entities) {
    if (!e.components.Goal) continue
    const gp = (e.components.Transform as { pos: Vec3 } | undefined)?.pos
    if (gp && distance(pp, gp) < GOAL_RADIUS) {
      ctx.setWin()
      return
    }
  }
}
