import type { Entity, Vec3 } from '@blenjs/core'
import { loadScene, type PrefabManifest, type RawGame, resolvePrefabs, resolveRefs } from '@blenjs/runtime-three'
import prefabsJson from '../../generated/prefabs.json'
import { registry } from '../components'
import { BULLET_SPEED, BULLET_TTL } from './constants'
import { getGame, resetGame, setGame } from './store'
import type { GameContext } from './types'

/** Prefab definitions aggregated by `bun run build:models`. */
const prefabs = prefabsJson as PrefabManifest

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
 * Load + validate a scene from the (already-parsed) game data and hydrate the
 * store. `game.json` is imported as a module, so the bundler hands us a parsed
 * object — no fetch, and editing the file triggers HMR. The player is spawned in
 * code at the PlayerSpawn marker (the emergent layer, spec §4) — note there is no
 * entity carrying the Player component in game.json.
 */
export const hydrateGame = (game: RawGame, sceneName = 'level1') => {
  const resolved = resolvePrefabs(game, sceneName, prefabs) // inline prefab defaults + overrides
  const { entities } = loadScene(resolved, sceneName, registry)
  resolveRefs(entities, registry) // throws (naming entity + field) if a ref dangles

  const map: Record<string, Entity> = {}
  const order: string[] = []
  for (const e of entities) {
    // fresh runtime scratch per load
    e.runtime = {}
    map[e.uuid] = e
    order.push(e.uuid)
  }

  // The player is the emergent layer (spawned in code, not authored in game.json).
  // Build it from the `player` prefab — same model + tuning as any instance — placed
  // at the PlayerSpawn marker, resolved through the very same prefab+load path.
  const spawn = entities.find(e => e.components.PlayerSpawn)
  const sp = (spawn?.components.Transform as { pos: Vec3 } | undefined)?.pos ?? [0, 2, 0]
  const playerGame: RawGame = {
    version: game.version,
    scenes: {
      [sceneName]: {
        entities: { [PLAYER_UUID]: { name: 'Player', prefab: 'player', Transform: { pos: [sp[0], sp[1], sp[2]] } } },
      },
    },
  }
  const player = loadScene(resolvePrefabs(playerGame, sceneName, prefabs), sceneName, registry).entities[0]
  player.runtime = {}
  map[player.uuid] = player
  order.push(player.uuid)

  resetGame()
  setGame({ entities: map, order })
}
