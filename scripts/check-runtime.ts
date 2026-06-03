import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  loadScene,
  parseGame,
  type PrefabManifest,
  resolvePrefabs,
  resolveRefs,
  ValidationError,
} from '@blenjs/runtime-three'
import prefabsJson from '../generated/prefabs.json'
import { registry } from '../app/components'

const prefabs = prefabsJson as PrefabManifest

/**
 * Headless smoke test of the runtime-three data path against the real game.json.
 * Proves JSON -> Zod validation -> entities -> UUID ref resolution, and that a
 * malformed value reports which component on which entity failed (spec §11).
 *
 *   bun run scripts/check-runtime.ts
 */
const here = dirname(fileURLToPath(import.meta.url))
const jsonText = readFileSync(resolve(here, '../game.json'), 'utf8')

let failures = 0
const assert = (cond: unknown, msg: string) => {
  if (cond) console.log(`  ✓ ${msg}`)
  else {
    failures++
    console.log(`  ✗ ${msg}`)
  }
}

console.log('resolvePrefabs + loadScene + resolveRefs on game.json (level1):')
const game = parseGame(jsonText)
const { entities, version } = loadScene(resolvePrefabs(game, 'level1', prefabs), 'level1', registry)
const { byId } = resolveRefs(entities, registry)

assert(version === registry.version, `schemaVersion ${version} matches registry`)
assert(entities.length === 16, `loaded 16 entities (got ${entities.length})`)

const enemy = entities.find(e => e.name === 'enemy_01')
const patrolData = enemy?.components.Patrol as { waypoints: string[] } | undefined
assert(!!patrolData, 'enemy_01 has Patrol')
const wps = patrolData?.waypoints ?? []
assert(wps.length === 2 && wps.every(w => byId.has(w)), 'enemy_01 waypoints resolve to real entities')

const spawn = entities.find(e => e.components.PlayerSpawn)
assert(!!spawn, 'a PlayerSpawn entity exists')
const goal = entities.find(e => e.components.Goal)
assert(!!goal, 'a Goal entity exists')

// Prefab resolution: a coin instance inherits its model + Pickup data from the prefab.
console.log('prefab resolution:')
const coin = entities.find(e => e.name === 'coin_01')
assert(
  (coin?.components.Model as { src?: string } | undefined)?.src === 'coin.glb',
  'coin_01 inherited Model.src=coin.glb',
)
assert(
  (coin?.components.Pickup as { kind?: string } | undefined)?.kind === 'coin',
  'coin_01 inherited Pickup.kind=coin',
)
const en = enemy?.components
assert(!!(en?.Model && en?.Enemy && en?.Damageable && en?.Patrol), 'enemy_01 inherited Model+Enemy+Damageable+Patrol')
assert(
  (en?.Patrol as { speed?: number } | undefined)?.speed === 2,
  'enemy_01 inherited Patrol.speed=2 (not overridden)',
)
const enemy2 = entities.find(e => e.name === 'enemy_02')
assert(
  (enemy2?.components.Patrol as { speed?: number } | undefined)?.speed === 1.5,
  'enemy_02 overrode Patrol.speed=1.5',
)

// Validation: a malformed component value must name component + entity.
console.log('validation error reporting:')
const bad = `{
  "version": 1,
  "scenes": {
    "level1": {
      "entities": {
        "deadbeef": {"name": "broken", "Pickup": {"kind": "invalid_kind", "value": -5}}
      }
    }
  }
}`
try {
  loadScene(parseGame(bad), 'level1', registry)
  assert(false, 'malformed Pickup should throw')
} catch (e) {
  const msg = e instanceof ValidationError ? e.message : String(e)
  assert(msg.includes('Pickup') && msg.includes('deadbeef'), 'error names component "Pickup" and entity "deadbeef"')
}

// Unresolved ref must be caught.
console.log('unresolved reference reporting:')
const dangling = `{
  "version": 1,
  "scenes": {
    "level1": {
      "entities": {
        "aaaa1111": {"name": "lonely", "Patrol": {"speed": 2, "waypoints": ["does_not_exist"], "loop": true}}
      }
    }
  }
}`
try {
  const r = loadScene(parseGame(dangling), 'level1', registry)
  resolveRefs(r.entities, registry)
  assert(false, 'dangling ref should throw')
} catch (e) {
  assert(String(e).includes('does_not_exist'), 'error names the missing reference')
}

// An unknown prefab reference must be caught (naming the prefab).
console.log('unknown prefab reporting:')
const badPrefab = '{"version":1,"scenes":{"level1":{"entities":{"c0ffee00":{"name":"x","prefab":"nope"}}}}}'
try {
  resolvePrefabs(parseGame(badPrefab), 'level1', prefabs)
  assert(false, 'unknown prefab should throw')
} catch (e) {
  assert(String(e).includes('nope'), 'error names the missing prefab "nope"')
}

console.log()
if (failures) {
  console.log(`✗ ${failures} runtime check(s) failed`)
  process.exit(1)
}
console.log('✓ all runtime checks passed')
