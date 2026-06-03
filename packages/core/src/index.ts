import { z } from 'zod'

/**
 * @blenjs/core — the registry + schema authority.
 *
 * Pure TypeScript + Zod. This package MUST NOT import three, react, or anything
 * Blender-specific. It is the runtime-agnostic core that keeps the vocabulary
 * publishable and reusable by non-R3F runtimes. Dependency arrows point strictly
 * outward from here (see the repo README, "Library organization").
 */

// Re-export the exact Zod instance so every layer (app, codegen, runtime) shares
// one copy and one set of schemas. Importing zod elsewhere is fine, but importing
// `z` from here guarantees instance identity for `instanceof` checks.
export { z }

/**
 * The schema-contract version. This is the real stability promise: it is embedded
 * in `components.schema.json` and in every .blen.json export so the runtime can detect
 * drift and migrate. Bump it whenever the *shape* of the contract changes.
 */
export const SCHEMA_VERSION = 1

// ---------------------------------------------------------------------------
// Editor metadata
// ---------------------------------------------------------------------------

/** Widget/marshalling hints read by codegen and the Blender add-on. */
export type BlenJSMeta = {
  /** How this field is rendered + serialized. Drives the Blender widget. */
  kind?: 'number' | 'int' | 'bool' | 'string' | 'enum' | 'vec2' | 'vec3' | 'vec4' | 'entityRef'
  /** Step for numeric sliders / Blender `step`. */
  step?: number
  /** Blender FloatVectorProperty subtype hint, e.g. 'XYZ', 'TRANSLATION', 'COLOR'. */
  subtype?: string
  /** Human tooltip surfaced in the Blender inspector. */
  tooltip?: string
}

/** Attach BlenJS editor metadata to any Zod schema node. */
export const meta = <T extends z.ZodType>(schema: T, m: BlenJSMeta): T => schema.meta({ blenjs: m }) as T

// ---------------------------------------------------------------------------
// Field helpers
// ---------------------------------------------------------------------------

/**
 * A reference to another entity. Branded so codegen and the Blender side know to
 * render it as an object reference (Blender `PointerProperty(type=Object)`) and
 * serialize it as a stable UUID string. At runtime it is just a UUID string.
 */
export type EntityRef = string

export const entityRef = () => z.string().meta({ blenjs: { kind: 'entityRef' } })

// Note: `.meta()` is applied LAST (after `.default()`) so the `blenjs` tag lands on
// the same JSON-Schema node as the default — this is what lets codegen classify the
// field as a vector rather than a generic array. Literal tuples keep Zod's typing of
// `.default()` precise.
export const vec2 = (def: Vec2 = [0, 0]) =>
  z
    .tuple([z.number(), z.number()])
    .default(def)
    .meta({ blenjs: { kind: 'vec2', subtype: 'XY' } })

export const vec3 = (def: Vec3 = [0, 0, 0]) =>
  z
    .tuple([z.number(), z.number(), z.number()])
    .default(def)
    .meta({ blenjs: { kind: 'vec3', subtype: 'XYZ' } })

/** A vector whose 4th component is typically W (or RGBA when used as a colour). */
export const vec4 = (def: Vec4 = [0, 0, 0, 0]) =>
  z
    .tuple([z.number(), z.number(), z.number(), z.number()])
    .default(def)
    .meta({ blenjs: { kind: 'vec4', subtype: 'COLOR' } })

// Convenience aliases for the literal vector types used across the codebase.
export type Vec2 = [number, number]
export type Vec3 = [number, number, number]
export type Vec4 = [number, number, number, number]

// ---------------------------------------------------------------------------
// Entities & systems
// ---------------------------------------------------------------------------

/** Validated component payload (a plain object keyed by field name). */
export type ComponentData = Record<string, unknown>

/**
 * A loaded entity. Identity is the UUID, never the name (Blender renames freely).
 * `components` is a flat map keyed by component name. `three` and `runtime` are
 * scratch space populated by the R3F runtime; the core treats them as opaque so
 * it stays renderer-agnostic.
 */
export type Entity = {
  uuid: string
  name: string
  components: Record<string, ComponentData>
  /** Captured Three.js object (Object3D) at runtime; typed opaque in core. */
  three?: unknown
  /** Per-entity scratch the runtime/systems may use (velocity, flags, …). */
  runtime?: Record<string, unknown>
}

/**
 * A system is the behavior half of a component. The runtime calls it once per
 * frame per entity that carries the component, passing the validated component
 * `data`, the frame delta, and a runtime-provided context. Keep systems pure
 * functions of `(entity, data, dt, ctx)`.
 *
 * The signature is intentionally loose here (`data`/`ctx` as `any`) so that the
 * core stays decoupled from any concrete runtime context type. Application
 * system files annotate their own `data`/`ctx` types for full safety.
 */
export type System = (entity: Entity, data: any, dt: number, ctx: any) => void

// ---------------------------------------------------------------------------
// defineComponent / defineRegistry
// ---------------------------------------------------------------------------

export type ComponentDef<S extends z.ZodObject = z.ZodObject> = {
  /** Component name — the JSON key and the registry key. Must be unique. */
  name: string
  /** Drives grouping in Blender's "Add Component" menu. */
  category: string
  /** Optional human description shown in the inspector. */
  tooltip?: string
  /** The Zod schema. The single validation + migration seam. */
  schema: S
  /**
   * The behavior. OMIT for pure-data components (e.g. Collider, Goal, PlayerSpawn).
   * A component with a system is what the spec calls a "behavior".
   */
  system?: System
}

/** Identity helper that preserves the precise schema type for `z.infer`. */
export const defineComponent = <S extends z.ZodObject>(def: ComponentDef<S>): ComponentDef<S> => def

export type Registry = {
  version: number
  components: ComponentDef[]
}

export const defineRegistry = (components: ComponentDef[], version: number = SCHEMA_VERSION): Registry => {
  const seen = new Set<string>()
  for (const c of components) {
    if (seen.has(c.name)) throw new Error(`Duplicate component in registry: "${c.name}"`)
    seen.add(c.name)
  }
  return { version, components }
}

/** Look up a component definition by name. */
export const getComponent = (registry: Registry, name: string): ComponentDef | undefined =>
  registry.components.find(c => c.name === name)

/** All component names in the registry. */
export const componentNames = (registry: Registry): string[] => registry.components.map(c => c.name)

/** Convenience type to extract a component's validated data shape. */
export type ComponentOf<D extends ComponentDef> = z.infer<D['schema']>
