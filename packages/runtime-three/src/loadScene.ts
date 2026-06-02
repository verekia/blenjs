import { getComponent, type Entity, type Registry } from '@blenjs/core'

/**
 * Raw, un-validated shape of `game.json` as parsed by `JSON.parse`. JSON typing is
 * strict (a number is a number, a string is a string), but each component payload
 * is still run through its Zod schema below to validate ranges, enums, and shape.
 */
export type RawEntity = { name?: string } & Record<string, unknown>
export type RawScene = { entities?: Record<string, RawEntity> }
export type RawGame = { version?: number; scenes?: Record<string, RawScene> }

/** Thrown when the parsed game data fails validation. Names the component + entity. */
export class ValidationError extends Error {
  override name = 'ValidationError'
}

export const parseGame = (jsonText: string): RawGame => (JSON.parse(jsonText) as RawGame | null) ?? {}

export type LoadResult = {
  version: number
  sceneName: string
  entities: Entity[]
}

export const sceneNames = (game: RawGame): string[] => Object.keys(game.scenes ?? {})

/**
 * Validate one scene against the registry's Zod schemas and return a flat list of
 * entities `{ uuid, name, components }`. Entity-ref fields remain UUID strings
 * here; call `resolveRefs` afterwards to verify they point at real entities.
 */
export const loadScene = (game: RawGame, sceneName: string, registry: Registry): LoadResult => {
  const version = game.version ?? 0
  if (version !== registry.version) {
    console.warn(
      `[blenjs] game.json schemaVersion ${version} != registry version ${registry.version}. ` +
        `Data may need migration.`,
    )
  }

  const scenes = game.scenes ?? {}
  const scene = scenes[sceneName]
  if (!scene) {
    throw new ValidationError(
      `Scene "${sceneName}" not found. Available scenes: ${Object.keys(scenes).join(', ') || '(none)'}`,
    )
  }

  const rawEntities = scene.entities ?? {}
  const entities: Entity[] = []
  const errors: string[] = []

  for (const uuid of Object.keys(rawEntities)) {
    const raw = rawEntities[uuid] ?? {}
    const name = typeof raw.name === 'string' ? raw.name : uuid
    const components: Record<string, Record<string, unknown>> = {}

    for (const key of Object.keys(raw)) {
      if (key === 'name') continue
      const def = getComponent(registry, key)
      if (!def) {
        errors.push(`Entity ${uuid} (${name}): unknown component "${key}" (not in registry)`)
        continue
      }
      const result = def.schema.safeParse(raw[key] ?? {})
      if (!result.success) {
        const issues = result.error.issues.map(i => `${i.path.join('.') || '(value)'}: ${i.message}`).join('; ')
        errors.push(`Component "${key}" on entity ${uuid} (${name}): ${issues}`)
        continue
      }
      components[key] = result.data as Record<string, unknown>
    }

    entities.push({ uuid, name, components })
  }

  if (errors.length) {
    throw new ValidationError(`Invalid game.json (${errors.length} problem(s)):\n - ${errors.join('\n - ')}`)
  }

  return { version, sceneName, entities }
}
