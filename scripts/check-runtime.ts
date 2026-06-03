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
 * Headless smoke test of the runtime-three data path against the real .blen.json.
 * Proves JSON -> Zod validation -> entities -> UUID ref resolution, and that a
 * malformed value reports which component on which entity failed (spec §11).
 *
 *   bun run scripts/check-runtime.ts
 */
const here = dirname(fileURLToPath(import.meta.url))
const jsonText = readFileSync(resolve(here, '../platformer.blen.json'), 'utf8')

let failures = 0
const assert = (cond: unknown, msg: string) => {
  if (cond) console.log(`  ✓ ${msg}`)
  else {
    failures++
    console.log(`  ✗ ${msg}`)
  }
}

console.log('resolvePrefabs + loadScene + resolveRefs on .blen.json (level1):')
const game = parseGame(jsonText)
const { entities, version } = loadScene(resolvePrefabs(game, 'level1', prefabs), 'level1', registry)
const { byId } = resolveRefs(entities, registry)

assert(version === registry.version, `schemaVersion ${version} matches registry`)
assert(entities.length === 21, `loaded 21 entities (got ${entities.length})`)

const enemy = entities.find(e => e.name === 'enemy_01')
const patrolData = enemy?.components.Patrol as { waypoints: string[] } | undefined
assert(!!patrolData, 'enemy_01 has Patrol')
const wps = patrolData?.waypoints ?? []
assert(wps.length === 2 && wps.every(w => byId.has(w)), 'enemy_01 waypoints resolve to real entities')

const spawn = entities.find(e => e.components.PlayerSpawn)
assert(!!spawn, 'a PlayerSpawn entity exists')
const goal = entities.find(e => e.components.Goal)
assert(!!goal, 'a Goal entity exists')

// Authored art outputs (TODO.md Tier 1): lights, camera, and material colours are data.
console.log('authored lights / camera / material:')
const lights = entities.filter(e => e.components.Light)
assert(lights.length === 2, `level1 authors 2 lights (got ${lights.length})`)
assert(
  lights.some(e => (e.components.Light as { type?: string }).type === 'ambient') &&
    lights.some(e => (e.components.Light as { type?: string }).type === 'directional'),
  'an ambient + a directional light are authored',
)
const camera = entities.find(e => e.components.Camera)
assert(
  (camera?.components.Camera as { zoom?: number } | undefined)?.zoom === 48,
  'a Camera entity is authored (zoom=48)',
)
const groundMat = entities.find(e => e.name === 'ground')?.components.Material as { color?: number[] } | undefined
assert(Array.isArray(groundMat?.color) && groundMat?.color?.length === 3, 'ground carries an authored Material colour')

// Event wiring (TODO.md Tier 2): a kill-volume Trigger replaces the old FALL_KILL_Z constant,
// and a "rune" Trigger removes target enemies — the entityRef wiring resolves to real entities.
console.log('event wiring (triggers):')
const triggers = entities.filter(e => e.components.Trigger)
assert(triggers.length === 2, `level1 authors 2 triggers (got ${triggers.length})`)
assert(
  triggers.some(e => (e.components.Trigger as { action?: string }).action === 'lose'),
  'a kill-volume trigger (action=lose) replaces the hardcoded fall plane',
)
const rune = entities.find(e => e.name === 'enemy_rune')?.components.Trigger as
  | { action?: string; targets?: string[] }
  | undefined
assert(
  rune?.action === 'remove' && (rune?.targets?.length ?? 0) === 2 && (rune?.targets ?? []).every(t => byId.has(t)),
  'enemy_rune removes 2 real target entities (trigger → targets wiring resolves)',
)

// Prefab resolution: a coin instance inherits its model + Pickup data from the prefab.
console.log('prefab resolution:')
const coin = entities.find(e => e.name === 'coin_01')
assert((coin?.components.Model as { src?: string } | undefined)?.src === 'coin', 'coin_01 inherited Model.src=coin')
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
