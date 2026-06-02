import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { loadScene, parseGame, resolveRefs, ValidationError } from '@blenjs/runtime-three'
import { registry } from '../app/components'

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

console.log('loadScene + resolveRefs on game.json (level1):')
const game = parseGame(jsonText)
const { entities, version } = loadScene(game, 'level1', registry)
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

console.log()
if (failures) {
  console.log(`✗ ${failures} runtime check(s) failed`)
  process.exit(1)
}
console.log('✓ all runtime checks passed')
