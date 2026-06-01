import { getComponent, z, type Entity, type Registry } from '@blenjs/core'

/**
 * Resolve entity-ref fields after all entities exist (spec §7.2). We mirror the
 * same UUID-keyed identity the Blender side uses: build a `uuid -> entity` map and
 * verify every entity-ref points at a real entity. Systems read refs lazily via
 * this map (kept as UUIDs in the data, resolved through `byId`), which avoids
 * circular object graphs in the store.
 */

export type ResolvedScene = {
  entities: Entity[]
  byId: Map<string, Entity>
}

type RefField = { field: string; array: boolean }

// Which top-level fields of a component are entity refs. Derived from the same
// reliable Zod JSON-Schema export codegen uses, then cached per registry.
const refCache = new WeakMap<Registry, Map<string, RefField[]>>()

const refFieldsFor = (registry: Registry, componentName: string): RefField[] => {
  let perRegistry = refCache.get(registry)
  if (!perRegistry) {
    perRegistry = new Map()
    refCache.set(registry, perRegistry)
  }
  const cached = perRegistry.get(componentName)
  if (cached) return cached

  const out: RefField[] = []
  const def = getComponent(registry, componentName)
  if (def) {
    const js = z.toJSONSchema(def.schema, { unrepresentable: 'any' }) as Record<string, any>
    const props = (js.properties ?? {}) as Record<string, any>
    for (const [field, node] of Object.entries(props)) {
      const inner = Array.isArray(node.anyOf) ? (node.anyOf.find((s: any) => s.type !== 'null') ?? {}) : node
      if (inner.blenjs?.kind === 'entityRef') out.push({ field, array: false })
      else if (inner.type === 'array' && inner.items?.blenjs?.kind === 'entityRef') out.push({ field, array: true })
    }
  }
  perRegistry.set(componentName, out)
  return out
}

export const resolveRefs = (entities: Entity[], registry: Registry): ResolvedScene => {
  const byId = new Map<string, Entity>()
  for (const e of entities) byId.set(e.uuid, e)

  const errors: string[] = []
  for (const e of entities) {
    for (const name of Object.keys(e.components)) {
      const data = e.components[name] as Record<string, unknown>
      for (const rf of refFieldsFor(registry, name)) {
        const value = data[rf.field]
        const refs = rf.array ? (Array.isArray(value) ? value : []) : value == null ? [] : [value]
        for (const ref of refs) {
          if (typeof ref === 'string' && ref.length > 0 && !byId.has(ref)) {
            errors.push(
              `Component "${name}" on entity ${e.uuid} (${e.name}): entityRef "${rf.field}" -> "${ref}" does not exist`,
            )
          }
        }
      }
    }
  }

  if (errors.length) {
    throw new Error(`Unresolved entity references (${errors.length}):\n - ${errors.join('\n - ')}`)
  }

  return { entities, byId }
}
