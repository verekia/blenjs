import { defineComponent, defineRegistry, entityRef, meta, rgb, vec3, z } from '@blenjs/core'
import { patrol, pickup, playerController, trigger } from './systems'

/**
 * The game vocabulary. This file is application content, not library — it USES
 * `@blenjs/core`'s `defineComponent` to declare the platformer's components. The
 * registry below is the schema authority that codegen turns into
 * `generated/components.schema.json`, which Blender reads.
 *
 * A component with a `system` is a "behavior"; without one it is pure data.
 * Systems are plain functions imported from `./systems` (kept free of any R3F /
 * WebGPU imports) so this module stays importable by the Node-only codegen.
 */

export const Transform = defineComponent({
  name: 'Transform',
  category: 'Core',
  tooltip: 'Position, rotation (Euler XYZ, radians) and scale.',
  schema: z.object({
    pos: vec3([0, 0, 0]),
    rot: vec3([0, 0, 0]),
    scale: vec3([1, 1, 1]),
  }),
})

export const Collider = defineComponent({
  name: 'Collider',
  category: 'Physics',
  tooltip: 'Solid volume. A box uses the entity Transform.scale as full size — parametric blockout, no .glb needed.',
  schema: z.object({
    // Required (no default) so it is always written — matches `Collider: { shape: box }`.
    shape: z.enum(['box', 'sphere', 'capsule']).meta({ blenjs: { tooltip: 'Collision shape' } }),
  }),
})

export const Model = defineComponent({
  name: 'Model',
  category: 'Rendering',
  tooltip:
    '3D model referenced by name. Blender links prefabs/<src>.blend; the runtime loads the built /assets/<src>.glb.',
  schema: z.object({
    src: meta(z.string().default(''), {
      tooltip: 'Model name, e.g. "coin" → prefabs/coin.blend (built to /assets/coin.glb)',
    }),
  }),
})

export const Light = defineComponent({
  name: 'Light',
  category: 'Rendering',
  tooltip:
    'A light source authored in Blender. Ambient lights fill the scene evenly (position ignored); directional lights shine from the entity position toward the world origin, like the sun.',
  schema: z.object({
    type: z
      .enum(['ambient', 'directional'])
      .default('directional')
      .meta({ blenjs: { tooltip: 'Ambient fill vs. a sun-like directional light' } }),
    color: rgb([1, 1, 1]),
    intensity: meta(z.number().min(0).max(20).default(1), { step: 0.1, tooltip: 'Brightness' }),
  }),
})

export const Camera = defineComponent({
  name: 'Camera',
  category: 'Rendering',
  tooltip:
    'The view camera. The entity Transform.pos is the camera position; it looks along +Y at the XZ play plane (the runtime follows the player from here).',
  schema: z.object({
    projection: z
      .enum(['orthographic', 'perspective'])
      .default('orthographic')
      .meta({ blenjs: { tooltip: 'Flat side-on (orthographic) vs. perspective' } }),
    zoom: meta(z.number().min(1).max(400).default(48), {
      step: 1,
      tooltip: 'Orthographic zoom (pixels per world unit)',
    }),
    fov: meta(z.number().min(1).max(170).default(50), { tooltip: 'Perspective field of view (degrees)' }),
    near: meta(z.number().min(0.001).max(100).default(0.1), { step: 0.1, tooltip: 'Near clip plane' }),
    far: meta(z.number().min(1).max(100000).default(1000), { tooltip: 'Far clip plane' }),
  }),
})

export const Material = defineComponent({
  name: 'Material',
  category: 'Rendering',
  tooltip:
    'Overrides the surface colour of a parametric primitive (platforms, goal, …). Model-backed entities keep their own glTF materials.',
  schema: z.object({
    color: rgb([0.8, 0.8, 0.8]),
    opacity: meta(z.number().min(0).max(1).default(1), { step: 0.05, tooltip: 'Transparency (1 = fully opaque)' }),
    unlit: z
      .boolean()
      .default(true)
      .meta({ blenjs: { tooltip: 'Flat colour (ignore lights) vs. shaded by the scene lights' } }),
  }),
})

export const Player = defineComponent({
  name: 'Player',
  category: 'Gameplay',
  tooltip: 'Marks the player avatar and tunes movement.',
  schema: z.object({
    moveSpeed: meta(z.number().min(0).max(40).default(6), { step: 0.1, tooltip: 'Horizontal speed (units/sec)' }),
    jumpForce: meta(z.number().min(0).max(40).default(11), { step: 0.1, tooltip: 'Initial jump velocity' }),
  }),
  system: playerController,
})

export const PlayerSpawn = defineComponent({
  name: 'PlayerSpawn',
  category: 'Gameplay',
  tooltip: 'Where the player is spawned at runtime. Pure marker (no fields).',
  schema: z.object({}),
})

export const Pickup = defineComponent({
  name: 'Pickup',
  category: 'Gameplay',
  tooltip: 'Collectible. Player overlap removes it and adds value to the score.',
  schema: z.object({
    kind: z
      .enum(['coin', 'gem', 'heart'])
      .default('coin')
      .meta({ blenjs: { tooltip: 'Pickup flavour' } }),
    value: meta(z.int().min(0).max(1000).default(10), { tooltip: 'Score awarded' }),
  }),
  system: pickup,
})

export const Enemy = defineComponent({
  name: 'Enemy',
  category: 'AI',
  tooltip: 'Marks a hostile entity.',
  schema: z.object({
    health: meta(z.int().min(1).max(100).default(3), { tooltip: 'Hit points' }),
  }),
})

export const Damageable = defineComponent({
  name: 'Damageable',
  category: 'Combat',
  tooltip: 'Takes damage from bullets; removed when health reaches 0.',
  schema: z.object({
    health: meta(z.int().min(1).max(100).default(3), { tooltip: 'Hit points' }),
  }),
})

export const Patrol = defineComponent({
  name: 'Patrol',
  category: 'AI',
  tooltip: 'Moves the entity between waypoint entities, turning at the ends.',
  schema: z.object({
    speed: meta(z.number().min(0).max(20).default(2), { step: 0.1, tooltip: 'Patrol speed (units/sec)' }),
    waypoints: z
      .array(entityRef())
      .default([])
      .meta({ blenjs: { tooltip: 'Ordered waypoint entities' } }),
    loop: z
      .boolean()
      .default(true)
      .meta({ blenjs: { tooltip: 'Cycle the path vs. ping-pong' } }),
  }),
  system: patrol,
})

export const Goal = defineComponent({
  name: 'Goal',
  category: 'Gameplay',
  tooltip: 'The level end trigger. Pure-data marker; win detection is a runtime system.',
  schema: z.object({}),
})

export const Trigger = defineComponent({
  name: 'Trigger',
  category: 'Logic',
  tooltip:
    'A non-solid volume (the entity scale is its full size) that fires an action when the player enters or exits — author interactions in Blender without code.',
  schema: z.object({
    on: z
      .enum(['enter', 'exit'])
      .default('enter')
      .meta({ blenjs: { tooltip: 'Fire when the player enters or exits the volume' } }),
    action: z
      .enum(['win', 'lose', 'remove'])
      .default('remove')
      .meta({ blenjs: { tooltip: 'win/lose end the level; remove deletes the targets' } }),
    targets: z
      .array(entityRef())
      .default([])
      .meta({ blenjs: { tooltip: 'Entities the "remove" action deletes (empty = the trigger itself)' } }),
    once: z
      .boolean()
      .default(true)
      .meta({ blenjs: { tooltip: 'Fire only the first time' } }),
  }),
  system: trigger,
})

/** The platformer registry — the order here drives system execution order. */
export const registry = defineRegistry([
  Transform,
  Collider,
  Model,
  Light,
  Camera,
  Material,
  Player,
  PlayerSpawn,
  Pickup,
  Enemy,
  Damageable,
  Patrol,
  Trigger,
  Goal,
])

// Convenience runtime types inferred from the schemas.
export type TransformData = z.infer<typeof Transform.schema>
export type ColliderData = z.infer<typeof Collider.schema>
export type ModelData = z.infer<typeof Model.schema>
export type LightData = z.infer<typeof Light.schema>
export type CameraData = z.infer<typeof Camera.schema>
export type MaterialData = z.infer<typeof Material.schema>
export type PlayerData = z.infer<typeof Player.schema>
export type PickupData = z.infer<typeof Pickup.schema>
export type EnemyData = z.infer<typeof Enemy.schema>
export type DamageableData = z.infer<typeof Damageable.schema>
export type PatrolData = z.infer<typeof Patrol.schema>
export type TriggerData = z.infer<typeof Trigger.schema>
