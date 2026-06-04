import type { Entity, Vec3 } from '@blenjs/core'

// Minimal AABB helpers — a platformer needs no heavy physics lib (spec §8).
export type AABB = { min: Vec3; max: Vec3 }

export const aabbFromCenter = (c: Vec3, half: Vec3): AABB => ({
  min: [c[0] - half[0], c[1] - half[1], c[2] - half[2]],
  max: [c[0] + half[0], c[1] + half[1], c[2] + half[2]],
})

// A small collision skin so AABBs that merely *touch* (share a face) do NOT count
// as overlapping — only genuine interpenetration does. This matters because the
// player controller sweeps one axis at a time, X before Y: when grounded, the
// player's bottom rests exactly on the platform top, so an inclusive (<=) test
// reported an overlap with the floor during the X sweep, which then snapped the
// player to the platform's far horizontal edge (pressing A/D while grounded
// teleported you across the platform). Mid-jump there's a real vertical gap, so it
// never triggered there. The skin is far below per-frame motion — gravity
// penetrates ~0.006/frame, walking ~0.1/frame — so landings and walls are
// unaffected, and far above float noise, so it's robust for arbitrary level scales.
const SKIN = 1e-4

export const overlap = (a: AABB, b: AABB): boolean =>
  a.min[0] < b.max[0] - SKIN &&
  a.max[0] > b.min[0] + SKIN &&
  a.min[1] < b.max[1] - SKIN &&
  a.max[1] > b.min[1] + SKIN &&
  a.min[2] < b.max[2] - SKIN &&
  a.max[2] > b.min[2] + SKIN

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

// ---------------------------------------------------------------------------
// Shaped colliders — Collider.shape (box | sphere | capsule), rotation-aware
// ---------------------------------------------------------------------------
// The player resolves against AXIS-ALIGNED boxes with the fast per-axis AABB sweep
// above (`colliderAABB` + the controller's `resolveAxis` — no rounding, the tuned
// platformer feel). A rotated box, a sphere, or a capsule instead uses a uniform
// "push the player (as a sphere) out of the shape" pass, so `Collider.shape` and
// rotation are honoured instead of silently ignored. Everything here is pure and
// covered by scripts/check-physics.ts.

export type ColliderShapeKind = 'box' | 'sphere' | 'capsule'

const ROT_EPS = 1e-4

const colliderRot = (e: Entity): Vec3 => (e.components.Transform as { rot?: Vec3 } | undefined)?.rot ?? [0, 0, 0]
const colliderShapeKind = (e: Entity): ColliderShapeKind =>
  (e.components.Collider as { shape?: ColliderShapeKind } | undefined)?.shape ?? 'box'
const isZeroRot = (r: Vec3) => Math.abs(r[0]) < ROT_EPS && Math.abs(r[1]) < ROT_EPS && Math.abs(r[2]) < ROT_EPS

/** True for a `box` collider with no rotation — the only case the fast AABB sweep handles.
 * Sphere, capsule, and rotated boxes go through `resolveSphereVsCollider` instead. */
export const isAxisAlignedBox = (e: Entity): boolean => colliderShapeKind(e) === 'box' && isZeroRot(colliderRot(e))

// --- tiny 3x3 rotation (three.js Euler 'XYZ': R = Rx·Ry·Rz; mirrors blender/transform.py) ---
type Mat3 = [number, number, number, number, number, number, number, number, number]
const matFromEulerXYZ = (r: Vec3): Mat3 => {
  const cx = Math.cos(r[0]),
    sx = Math.sin(r[0])
  const cy = Math.cos(r[1]),
    sy = Math.sin(r[1])
  const cz = Math.cos(r[2]),
    sz = Math.sin(r[2])
  return [
    cy * cz,
    -cy * sz,
    sy,
    sx * sy * cz + cx * sz,
    -sx * sy * sz + cx * cz,
    -sx * cy,
    -cx * sy * cz + sx * sz,
    cx * sy * sz + sx * cz,
    cx * cy,
  ]
}
const mul = (m: Mat3, v: Vec3): Vec3 => [
  m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
  m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
  m[6] * v[0] + m[7] * v[1] + m[8] * v[2],
]
const mulT = (m: Mat3, v: Vec3): Vec3 => [
  m[0] * v[0] + m[3] * v[1] + m[6] * v[2],
  m[1] * v[0] + m[4] * v[1] + m[7] * v[2],
  m[2] * v[0] + m[5] * v[1] + m[8] * v[2],
]

export type PushOut = { normal: Vec3; depth: number }

const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
const lenV = (v: Vec3): number => Math.hypot(v[0], v[1], v[2])

// Resolve a moving sphere (the player) against a static sphere — the shared core for
// sphere and capsule colliders. Returns the outward normal + penetration, or null.
const sphereVsSphere = (center: Vec3, radius: number, c2: Vec3, r2: number): PushOut | null => {
  const d = sub(center, c2)
  const dist = lenV(d)
  const sum = radius + r2
  if (dist >= sum) return null
  if (dist < 1e-6) return { normal: [0, 0, 1], depth: sum } // concentric → push straight up
  return { normal: [d[0] / dist, d[1] / dist, d[2] / dist], depth: sum - dist }
}

const closestOnSegment = (p: Vec3, a: Vec3, b: Vec3): Vec3 => {
  const ab = sub(b, a)
  const denom = ab[0] * ab[0] + ab[1] * ab[1] + ab[2] * ab[2]
  if (denom < 1e-12) return [a[0], a[1], a[2]]
  let t = ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1] + (p[2] - a[2]) * ab[2]) / denom
  t = t < 0 ? 0 : t > 1 ? 1 : t
  return [a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t]
}

const sphereVsObb = (center: Vec3, radius: number, boxC: Vec3, half: Vec3, rot: Vec3): PushOut | null => {
  const m = matFromEulerXYZ(rot)
  const local = mulT(m, sub(center, boxC)) // world → box-local (inverse rotation)
  if (Math.abs(local[0]) <= half[0] && Math.abs(local[1]) <= half[1] && Math.abs(local[2]) <= half[2]) {
    // sphere centre is inside the box: eject along the least-penetrated local axis.
    const pen: Vec3 = [half[0] - Math.abs(local[0]), half[1] - Math.abs(local[1]), half[2] - Math.abs(local[2])]
    let axis = 0
    if (pen[1] < pen[axis]) axis = 1
    if (pen[2] < pen[axis]) axis = 2
    const nLocal: Vec3 = [0, 0, 0]
    nLocal[axis] = local[axis] >= 0 ? 1 : -1
    return { normal: mul(m, nLocal), depth: pen[axis] + radius }
  }
  const cl: Vec3 = [
    Math.max(-half[0], Math.min(half[0], local[0])),
    Math.max(-half[1], Math.min(half[1], local[1])),
    Math.max(-half[2], Math.min(half[2], local[2])),
  ]
  const off = mul(m, cl)
  const closest: Vec3 = [boxC[0] + off[0], boxC[1] + off[1], boxC[2] + off[2]]
  const d = sub(center, closest)
  const dist = lenV(d)
  if (dist >= radius) return null
  if (dist < 1e-6) return { normal: [0, 0, 1], depth: radius }
  return { normal: [d[0] / dist, d[1] / dist, d[2] / dist], depth: radius - dist }
}

/**
 * Push the player sphere (`center`, `radius`) out of a sphere / capsule / rotated-box
 * collider. Returns the world-space outward normal and penetration depth, or null when
 * not overlapping. Shape sizing from `Transform.scale`: a sphere's radius and a capsule's
 * radius/height are derived from the scale box; a box uses scale as full extents. (Used
 * only for non-axis-aligned colliders — see `isAxisAlignedBox`.)
 */
export const resolveSphereVsCollider = (center: Vec3, radius: number, e: Entity): PushOut | null => {
  const t = e.components.Transform as { pos?: Vec3; rot?: Vec3; scale?: Vec3 } | undefined
  if (!t?.pos) return null
  const c = t.pos
  const s = t.scale ?? [1, 1, 1]
  const kind = colliderShapeKind(e)
  if (kind === 'sphere') return sphereVsSphere(center, radius, c, 0.5 * Math.max(s[0], s[1], s[2]))
  if (kind === 'capsule') {
    const r = 0.5 * Math.max(s[0], s[1])
    const halfH = Math.max(0, 0.5 * s[2] - r) // segment half-length between the two cap centres
    const rot = t.rot ?? [0, 0, 0]
    const axis = isZeroRot(rot) ? ([0, 0, 1] as Vec3) : mul(matFromEulerXYZ(rot), [0, 0, 1])
    const a: Vec3 = [c[0] - axis[0] * halfH, c[1] - axis[1] * halfH, c[2] - axis[2] * halfH]
    const b: Vec3 = [c[0] + axis[0] * halfH, c[1] + axis[1] * halfH, c[2] + axis[2] * halfH]
    return sphereVsSphere(center, radius, closestOnSegment(center, a, b), r)
  }
  return sphereVsObb(center, radius, c, [s[0] / 2, s[1] / 2, s[2] / 2], t.rot ?? [0, 0, 0])
}

export type PushApply = { dx: number; dy: number; dz: number; vx: number; vz: number; grounded: boolean }

/**
 * Apply a shape push-out to the grounded platformer player. An obstacle may push the player UP
 * (stand on top) or sideways, but **never DOWN**: a downward push would embed the player in the
 * floor box, and the per-axis box sweep would then snap them to its far edge (the "teleport to
 * the platform edge" bug when walking into the lower half of a boulder/capsule). So a downward
 * normal is flattened to its horizontal part. Returns the position delta, the velocity after
 * cancelling the into-surface component, and whether this grounds the player. Pure (tested).
 */
export const applyGroundedPushOut = (hit: PushOut, vx: number, vz: number): PushApply => {
  let [nx, ny, nz] = hit.normal
  if (nz < 0) nz = 0 // never push the player down into the floor
  const vn = vx * nx + vz * nz
  if (vn < 0) {
    vx -= vn * nx
    vz -= vn * nz
  }
  return { dx: nx * hit.depth, dy: ny * hit.depth, dz: nz * hit.depth, vx, vz, grounded: nz > 0.5 }
}
