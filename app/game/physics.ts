import type { Entity, Vec3 } from '@blenjs/core'

// Minimal AABB helpers — a platformer needs no heavy physics lib (spec §8).
export type AABB = { min: Vec3; max: Vec3 }

export const aabbFromCenter = (c: Vec3, half: Vec3): AABB => ({
  min: [c[0] - half[0], c[1] - half[1], c[2] - half[2]],
  max: [c[0] + half[0], c[1] + half[1], c[2] + half[2]],
})

export const overlap = (a: AABB, b: AABB): boolean =>
  a.min[0] <= b.max[0] &&
  a.max[0] >= b.min[0] &&
  a.min[1] <= b.max[1] &&
  a.max[1] >= b.min[1] &&
  a.min[2] <= b.max[2] &&
  a.max[2] >= b.min[2]

/**
 * The solid box for a Collider entity. Box size is parametric: a Collider has no
 * size of its own — it uses the entity's `Transform.scale` as full extents. This
 * is what lets blockout platforms be pure data with no .glb (spec §5).
 */
export const colliderAABB = (e: Entity): AABB | null => {
  const t = e.components.Transform as { pos?: Vec3; scale?: Vec3 } | undefined
  if (!t?.pos) return null
  const size = t.scale ?? [1, 1, 1]
  const half: Vec3 = [size[0] / 2, size[1] / 2, size[2] / 2]
  return aabbFromCenter(t.pos, half)
}

export const distance = (a: Vec3, b: Vec3): number => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])
