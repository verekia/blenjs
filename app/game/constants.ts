import type { Vec3 } from '@blenjs/core'

// Tuning for the platformer. All units are world units; the level lives in the XY
// plane (X = horizontal, Y = vertical/jump) with Z used only for visual depth.
export const GRAVITY = -24
export const PLAYER_HALF: Vec3 = [0.4, 0.5, 0.4]
export const MAX_AMMO = 20
export const BULLET_SPEED = 18
export const BULLET_TTL = 1.4
export const BULLET_HIT_RADIUS = 0.7
export const FIRE_COOLDOWN = 0.18
export const PICKUP_RADIUS = 0.9
export const GOAL_RADIUS = 1.2
export const FALL_KILL_Y = -25
