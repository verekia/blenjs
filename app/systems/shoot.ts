import type { Vec3 } from '@blenjs/core'
import { BULLET_HIT_RADIUS, FIRE_COOLDOWN } from '../game/constants'
import { distance } from '../game/physics'
import { getGame, setGame } from '../game/store'
import type { Bullet, GameContext } from '../game/types'
import type { PlayerRuntime } from './playerController'

/**
 * The shoot feature is the "emergent layer is code" example (spec §4, §7.6):
 * bullets are spawned at runtime, not authored in JSON. `shootStep` fires from the
 * player; `bulletStep` advances bullets and damages `Damageable` entities on
 * contact. Both run as runtime systems (not attached to a registry component).
 */
export const shootStep = (dt: number, ctx: GameContext) => {
  const player = ctx.player
  if (!player) return
  const rt = (player.runtime ??= {}) as Partial<PlayerRuntime>
  rt.fireCd = Math.max(0, (rt.fireCd ?? 0) - dt)
  if (!ctx.input.shoot || rt.fireCd > 0) return

  const pos = (player.components.Transform as { pos: Vec3 } | undefined)?.pos
  if (!pos) return
  const dir = rt.dir ?? 1
  const fired = ctx.spawnBullet([pos[0] + dir * 0.6, pos[1], pos[2]], dir)
  if (fired) rt.fireCd = FIRE_COOLDOWN
}

export const bulletStep = (dt: number, ctx: GameContext) => {
  const { bullets } = getGame()
  if (bullets.length === 0) return

  const survivors: Bullet[] = []
  let changed = false

  for (const b of bullets) {
    b.ttl -= dt
    b.pos[0] += b.vel[0] * dt
    b.pos[1] += b.vel[1] * dt
    b.pos[2] += b.vel[2] * dt

    if (b.ttl <= 0) {
      changed = true
      continue
    }

    let hit = false
    for (const e of ctx.entities) {
      const dmg = e.components.Damageable as { health: number } | undefined
      const tp = (e.components.Transform as { pos: Vec3 } | undefined)?.pos
      if (!dmg || !tp) continue
      if (distance(b.pos, tp) < BULLET_HIT_RADIUS) {
        dmg.health -= 1
        hit = true
        if (dmg.health <= 0) ctx.removeEntity(e.uuid)
        break
      }
    }
    if (hit) {
      changed = true
      continue
    }
    survivors.push(b)
  }

  if (changed) setGame({ bullets: survivors })
}
