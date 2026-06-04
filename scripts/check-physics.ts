import type { Entity } from '@blenjs/core'
import { applyGroundedPushOut, isAxisAlignedBox, resolveSphereVsCollider } from '../app/game/physics'

/**
 * Pure-math checks for shaped colliders (Collider.shape = box | sphere | capsule, and box
 * rotation). The player is modelled as a sphere; these prove the push-out normal/depth so the
 * collision fix is verifiable without a GPU/browser.
 *
 *   bun run scripts/check-physics.ts
 */
const ent = (shape: string, pos: number[], scale: number[], rot: number[] = [0, 0, 0]): Entity =>
  ({ uuid: 'x', name: 'x', components: { Transform: { pos, rot, scale }, Collider: { shape } } }) as unknown as Entity

let failures = 0
const assert = (cond: unknown, msg: string) => {
  if (cond) console.log(`  ✓ ${msg}`)
  else {
    failures++
    console.log(`  ✗ ${msg}`)
  }
}
const near = (a: number, b: number, eps = 1e-6) => Math.abs(a - b) < eps

console.log('axis-aligned box detection (which path a collider takes):')
assert(isAxisAlignedBox(ent('box', [0, 0, 0], [2, 2, 2])), 'an un-rotated box uses the fast AABB sweep')
assert(!isAxisAlignedBox(ent('box', [0, 0, 0], [2, 2, 2], [0.3, 0, 0])), 'a rotated box uses the push-out path')
assert(!isAxisAlignedBox(ent('sphere', [0, 0, 0], [2, 2, 2])), 'a sphere uses the push-out path')
assert(!isAxisAlignedBox(ent('capsule', [0, 0, 0], [1, 1, 3])), 'a capsule uses the push-out path')

console.log('sphere collider (radius = 0.5·max scale = 1.0; player radius 0.4):')
const sphere = ent('sphere', [0, 0, 0], [2, 2, 2])
let hit = resolveSphereVsCollider([0, 0, 1.2], 0.4, sphere)
assert(!!hit && hit.normal[2] > 0.99, 'player above the sphere is pushed +Z (lands on top)')
assert(!!hit && near(hit.depth, 0.2), 'penetration depth = (1.0+0.4) − 1.2 = 0.2')
hit = resolveSphereVsCollider([1.3, 0, 0], 0.4, sphere)
assert(!!hit && hit.normal[0] > 0.99 && near(hit.depth, 0.1), 'player beside the sphere is pushed +X by 0.1')
assert(resolveSphereVsCollider([0, 0, 2.0], 0.4, sphere) === null, 'player clear of the sphere → no hit')

console.log('capsule collider (scale [1,1,3] → radius 0.5, cap centres at z ±1.0):')
const cap = ent('capsule', [0, 0, 0], [1, 1, 3])
hit = resolveSphereVsCollider([0.8, 0, 0], 0.4, cap)
assert(!!hit && hit.normal[0] > 0.99 && near(hit.depth, 0.1), 'player beside the cylinder pushed +X by 0.1')
hit = resolveSphereVsCollider([0, 0, 1.0], 0.4, cap)
assert(!!hit && hit.normal[2] > 0.99, 'player above the top cap centre pushed +Z')
assert(resolveSphereVsCollider([0, 0, 2.0], 0.4, cap) === null, 'player above the capsule (cap at z=1.5) → no hit')

console.log('rotated box collider (2×2×2 box turned 45° about Z):')
const rbox = ent('box', [0, 0, 0], [2, 2, 2], [0, 0, Math.PI / 4])
// The 45° box reaches its corner at x ≈ √2 ≈ 1.414; a player at x=1.5 (r 0.4) overlaps near it.
hit = resolveSphereVsCollider([1.5, 0, 0], 0.4, rbox)
assert(!!hit && hit.normal[0] > 0.5, 'player against the rotated box is pushed roughly +X')
assert(resolveSphereVsCollider([3, 0, 0], 0.4, rbox) === null, 'player well clear of the rotated box → no hit')
// Same player position, but the box un-rotated only reaches x=1.0, so x=1.5 (r0.4) is clear:
assert(
  resolveSphereVsCollider([1.5, 0, 0], 0.4, ent('box', [0, 0, 0], [2, 2, 2])) === null,
  'rotation matters: the un-rotated box does NOT reach the same point',
)

console.log('grounded push-out — an obstacle never pushes the player DOWN into the floor:')
// Walk LEFT into the lower hemisphere of a boulder resting on the ground (normal points
// right-and-DOWN). The downward push must be dropped, else the player embeds in the ground box
// and the per-axis sweep snaps them to its far X edge (the reported teleport bug).
let push = applyGroundedPushOut({ normal: [0.97, 0, -0.24], depth: 0.12 }, -6, 0)
assert(push.dz === 0, 'a downward push is clamped to zero (no sinking into the floor)')
assert(push.dx > 0, 'the player is still pushed horizontally out of the obstacle')
assert(push.vz >= 0, 'no downward velocity is injected (walking into a boulder cannot sink you)')
assert(push.vx > -6 && push.vx <= 0, 'the leftward velocity heading into the surface is cancelled')
// Standing on TOP of a sphere (normal up) still grounds the player and stops the fall.
push = applyGroundedPushOut({ normal: [0, 0, 1], depth: 0.1 }, 0, -8)
assert(push.dz > 0 && push.grounded && push.vz === 0, 'landing on top of a shape grounds the player')
// Direct regression on the real boulder geometry: player in its lower hemisphere → no down push.
const boulder = ent('sphere', [-1.5, 0, 1.25], [1.5, 1.5, 1.5])
const bhit = resolveSphereVsCollider([-0.55, 0, 1.0], 0.4, boulder)
assert(!!bhit && bhit.normal[2] < 0, 'boulder lower-hemisphere contact has a downward raw normal…')
assert(!!bhit && applyGroundedPushOut(bhit, -6, 0).dz === 0, '…which the grounded push-out flattens (no teleport)')

console.log()
if (failures) {
  console.log(`✗ ${failures} physics check(s) failed`)
  process.exit(1)
}
console.log('✓ all physics checks passed')
