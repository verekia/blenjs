import { ValidationError, type RawEntity, type RawGame } from './loadScene'

/**
 * Prefab resolution (the layer above `loadScene`). A prefab is a *named entity
 * template* authored under `prefabs/<name>.json` and aggregated into
 * `generated/prefabs.json`. A `game.json` entity references one with the reserved
 * `prefab` key and overrides it:
 *
 *   "5f6102bd": { "name": "coin_01", "prefab": "coin",
 *                 "Transform": { "pos": [5,0,3] }, "Pickup": { "value": 50 } }
 *
 * We merge prefab + overrides at the RAW (pre-Zod) level so a partial override
 * (e.g. `Pickup.value` alone) keeps the prefab's other fields (`kind`) and Zod
 * fills any still-missing defaults afterwards. The result is a plain scene of
 * entities the existing `loadScene` already understands — the prefab key is gone,
 * the prefab's components (including its `Model`) are inlined.
 */

/** One component's payload, keyed by field. */
export type PrefabComponents = Record<string, Record<string, unknown>>
/** A prefab definition: a name and the component set it stamps. */
export type PrefabDef = { name?: string; components: PrefabComponents }
/** `generated/prefabs.json` — prefab name -> definition. */
export type PrefabManifest = Record<string, PrefabDef>

// Entity-level keys that are not components.
const RESERVED = new Set(['name', 'prefab'])

/**
 * Overlay instance components onto prefab components, field by field (instance
 * wins). Each component is shallow-copied so the shared manifest object is never
 * mutated; a component absent from the instance is inherited whole.
 */
const mergeComponents = (base: PrefabComponents, instance: RawEntity): Record<string, unknown> => {
  const out: Record<string, unknown> = {}
  for (const [name, data] of Object.entries(base)) out[name] = { ...data }
  for (const key of Object.keys(instance)) {
    if (RESERVED.has(key)) continue
    const over = instance[key]
    if (over && typeof over === 'object' && !Array.isArray(over)) {
      out[key] = { ...(out[key] as Record<string, unknown>), ...(over as Record<string, unknown>) }
    } else {
      out[key] = over // non-object component value (unusual) replaces wholesale
    }
  }
  return out
}

/**
 * Resolve every prefab instance in one scene. Returns a new `RawGame` with that
 * scene's entities flattened; other scenes pass through untouched. Throws a
 * `ValidationError` (naming entity + prefab) if a referenced prefab is missing,
 * mirroring `resolveRefs`'s error style.
 */
export const resolvePrefabs = (game: RawGame, sceneName: string, prefabs: PrefabManifest): RawGame => {
  const scene = game.scenes?.[sceneName]
  if (!scene) return game // let loadScene throw the precise "scene not found"

  const rawEntities = scene.entities ?? {}
  const out: Record<string, RawEntity> = {}
  const errors: string[] = []

  for (const uuid of Object.keys(rawEntities)) {
    const raw = rawEntities[uuid] ?? {}
    const prefabName = typeof raw.prefab === 'string' ? raw.prefab : undefined
    if (!prefabName) {
      out[uuid] = raw
      continue
    }
    const def = prefabs[prefabName]
    if (!def) {
      errors.push(`Entity ${uuid} (${raw.name ?? uuid}): unknown prefab "${prefabName}"`)
      out[uuid] = raw
      continue
    }
    const name = typeof raw.name === 'string' ? raw.name : def.name
    out[uuid] = { name, ...mergeComponents(def.components ?? {}, raw) }
  }

  if (errors.length) {
    throw new ValidationError(`Unresolved prefabs (${errors.length}):\n - ${errors.join('\n - ')}`)
  }

  return { ...game, scenes: { ...game.scenes, [sceneName]: { entities: out } } }
}
