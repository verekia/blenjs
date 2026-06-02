import type { Vec3 } from '@blenjs/core'

// Tuning for the platformer. All units are world units. The world is Z-up
// right-handed (same as Blender): X = horizontal, Z = vertical/jump, Y = depth.
// The level lives in the XZ plane with Y used only for visual depth.
export const GRAVITY = -24
export const PLAYER_HALF: Vec3 = [0.4, 0.4, 0.5]
export const MAX_AMMO = 20
export const BULLET_SPEED = 18
export const BULLET_TTL = 1.4
export const BULLET_HIT_RADIUS = 0.7
export const FIRE_COOLDOWN = 0.18
export const PICKUP_RADIUS = 0.9
export const GOAL_RADIUS = 1.2
export const FALL_KILL_Z = -25
