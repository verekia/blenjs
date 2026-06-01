import { writeFileSync } from 'node:fs'
import { z, type Registry } from '@blenjs/core'

/**
 * @blenjs/codegen — turns the TS registry into `generated/components.schema.json`.
 *
 * Node-only. Depends only on @blenjs/core (which owns the vocabulary). This file
 * owns the *contract format* that the Blender add-on reads off disk, so the format
 * is versioned via `schemaVersion`. Keep it in lockstep with the add-on.
 *
 * Strategy (per spec §4): use Zod's JSON-Schema export as the base, then enrich
 * each field with the editor metadata Blender needs (type, default, widget hints,
 * and an explicit mark for entity-ref fields).
 */

export type FieldType = 'number' | 'int' | 'bool' | 'string' | 'enum' | 'vec2' | 'vec3' | 'vec4' | 'entityRef' | 'array'

export type SchemaField = {
  name: string
  type: FieldType
  /** Element type when `type === 'array'`. */
  itemType?: FieldType
  /** True when the Zod schema has no default — Blender always emits these. */
  required: boolean
  default?: unknown
  nullable?: boolean
  min?: number
  max?: number
  step?: number
  /** Blender FloatVectorProperty subtype hint (XYZ, COLOR, …). */
  subtype?: string
  /** Allowed values when `type === 'enum'`. */
  enumValues?: string[]
  tooltip?: string
}

export type SchemaComponent = {
  name: string
  category: string
  tooltip?: string
  /** A behavior component (has a registered system) vs. pure data. */
  hasSystem: boolean
  fields: SchemaField[]
  /** The raw Zod JSON-Schema export, embedded so the contract is self-describing. */
  jsonSchema: unknown
}

export type SchemaDocument = {
  schemaVersion: number
  generatedBy: string
  components: SchemaComponent[]
}

type JsonNode = Record<string, any>

// JS numbers Zod emits as sentinel bounds for unbounded integers/numbers.
const isSentinel = (v: number) => Math.abs(v) >= Number.MAX_SAFE_INTEGER

/** Resolve a possibly-nullable node down to its meaningful schema + nullability. */
const unwrapNullable = (node: JsonNode): { inner: JsonNode; nullable: boolean } => {
  if (Array.isArray(node.anyOf)) {
    const nullable = node.anyOf.some((s: JsonNode) => s.type === 'null')
    const inner = node.anyOf.find((s: JsonNode) => s.type !== 'null') ?? {}
    return { inner, nullable }
  }
  return { inner: node, nullable: false }
}

const classify = (n: JsonNode): { type: FieldType; itemType?: FieldType; enumValues?: string[] } => {
  const kind = n.blenjs?.kind as string | undefined
  if (kind === 'entityRef') return { type: 'entityRef' }
  if (kind === 'vec2' || kind === 'vec3' || kind === 'vec4') return { type: kind }
  if (Array.isArray(n.enum)) return { type: 'enum', enumValues: n.enum as string[] }
  if (n.type === 'integer') return { type: 'int' }
  if (n.type === 'number') return { type: 'number' }
  if (n.type === 'boolean') return { type: 'bool' }
  if (n.type === 'array') {
    const items = (n.items ?? {}) as JsonNode
    const itemKind = items.blenjs?.kind as string | undefined
    const itemType: FieldType = itemKind === 'entityRef' ? 'entityRef' : ((items.type as FieldType) ?? 'string')
    return { type: 'array', itemType }
  }
  return { type: 'string' }
}

const fieldFromNode = (name: string, node: JsonNode): SchemaField => {
  const { inner, nullable } = unwrapNullable(node)
  const blen = (inner.blenjs ?? {}) as Record<string, any>
  const { type, itemType, enumValues } = classify(inner)

  const field: SchemaField = {
    name,
    type,
    required: !('default' in node),
  }
  if (itemType) field.itemType = itemType
  if (nullable) field.nullable = true
  if ('default' in node) field.default = node.default
  if (typeof inner.minimum === 'number' && !isSentinel(inner.minimum)) field.min = inner.minimum
  if (typeof inner.maximum === 'number' && !isSentinel(inner.maximum)) field.max = inner.maximum
  if (typeof blen.step === 'number') field.step = blen.step
  if (typeof blen.subtype === 'string') field.subtype = blen.subtype
  if (enumValues) field.enumValues = enumValues
  const tooltip = blen.tooltip ?? inner.description
  if (typeof tooltip === 'string') field.tooltip = tooltip
  return field
}

/** Build the enriched schema document from a registry (pure — no disk writes). */
export const generateSchema = (registry: Registry): SchemaDocument => {
  const components: SchemaComponent[] = registry.components.map(def => {
    const jsonSchema = z.toJSONSchema(def.schema, { unrepresentable: 'any' }) as JsonNode
    const props = (jsonSchema.properties ?? {}) as Record<string, JsonNode>
    const fields = Object.entries(props).map(([name, node]) => fieldFromNode(name, node))
    const component: SchemaComponent = {
      name: def.name,
      category: def.category,
      hasSystem: Boolean(def.system),
      fields,
      jsonSchema,
    }
    if (def.tooltip) component.tooltip = def.tooltip
    return component
  })

  return {
    schemaVersion: registry.version,
    generatedBy: '@blenjs/codegen',
    components,
  }
}

/** Generate and write `components.schema.json` deterministically (committed file). */
export const writeSchema = (registry: Registry, outPath: string): SchemaDocument => {
  const doc = generateSchema(registry)
  writeFileSync(outPath, `${JSON.stringify(doc, null, 2)}\n`, 'utf8')
  return doc
}
