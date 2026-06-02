import type { Entity, Vec3 } from '@blenjs/core'
import { loadScene, parseGame, resolveRefs } from '@blenjs/runtime-three'
import { Player, registry } from '../components'
import { BULLET_SPEED, BULLET_TTL } from './constants'
import { getGame, resetGame, setGame } from './store'
import type { GameContext } from './types'

export const PLAYER_UUID = '__player__'

/**
 * Build the per-frame system context from the store. Cheap for a small level; all
 * world mutation flows through the closures here so systems stay pure.
 */
export const makeContext = (dt: number, elapsed: number): GameContext => {
  const s = getGame()
  const entities = s.order.map(id => s.entities[id]).filter(Boolean) as Entity[]
  const colliders = entities.filter(e => e.components.Collider)
  const player = entities.find(e => e.components.Player)

  return {
    dt,
    elapsed,
    entities,
    colliders,
    player,
    getEntity: id => getGame().entities[id],
    input: s.input,
    spawnBullet: (pos: Vec3, dirX: number) => {
      const st = getGame()
      if (st.ammo <= 0) return false
      const bullet = {
        id: st.nextBulletId,
        pos: [pos[0], pos[1], pos[2]] as Vec3,
        vel: [dirX * BULLET_SPEED, 0, 0] as Vec3,
        ttl: BULLET_TTL,
      }
      setGame({ bullets: [...st.bullets, bullet], nextBulletId: st.nextBulletId + 1, ammo: st.ammo - 1 })
      return true
    },
    addScore: n => setGame({ score: getGame().score + n }),
    removeEntity: uuid => {
      const st = getGame()
      if (!st.entities[uuid]) return
      const next = { ...st.entities }
      delete next[uuid]
      setGame({ entities: next, order: st.order.filter(id => id !== uuid) })
    },
    setWin: () => {
      if (!getGame().win && !getGame().lose) setGame({ win: true })
    },
    setLose: () => {
      if (!getGame().lose && !getGame().win) setGame({ lose: true })
    },
  }
}

/**
 * Load + validate a scene from a JSON string and hydrate the store. The player is
 * spawned in code at the PlayerSpawn marker (the emergent layer, spec §4) — note
 * there is no entity carrying the Player component in game.json.
 */
export const hydrateFromJson = (jsonText: string, sceneName = 'level1') => {
  const game = parseGame(jsonText)
  const { entities } = loadScene(game, sceneName, registry)
  resolveRefs(entities, registry) // throws (naming entity + field) if a ref dangles

  const map: Record<string, Entity> = {}
  const order: string[] = []
  for (const e of entities) {
    // fresh runtime scratch per load
    e.runtime = {}
    map[e.uuid] = e
    order.push(e.uuid)
  }

  const spawn = entities.find(e => e.components.PlayerSpawn)
  const sp = (spawn?.components.Transform as { pos: Vec3 } | undefined)?.pos ?? [0, 2, 0]
  const player: Entity = {
    uuid: PLAYER_UUID,
    name: 'Player',
    components: {
      Transform: { pos: [sp[0], sp[1], sp[2]], rot: [0, 0, 0], scale: [1, 1, 1] },
      Player: Player.schema.parse({}),
    },
    runtime: {},
  }
  map[player.uuid] = player
  order.push(player.uuid)

  resetGame()
  setGame({ entities: map, order })
}

export const fetchAndHydrate = async (url = '/game.json', sceneName = 'level1') => {
  const res = await fetch(url, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to fetch ${url}: ${res.status}`)
  hydrateFromJson(await res.text(), sceneName)
}
