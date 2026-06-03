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

// --- Facing -----------------------------------------------------------------
// Entities turn to face their movement direction with a yaw around the up axis
// (Z). The character models are authored facing -Y (toward the camera at rest);
// a +90° yaw turns that to face +X, so the applied yaw is `heading + this offset`.
// (Flip by π if a model turns out to face away from its movement.)
export const MODEL_YAW_OFFSET = Math.PI / 2
// Angular damping toward the target heading (higher = snappier turns).
export const TURN_LERP = 12

// --- Camera (locked orthogonal to the XZ plane; classic dead-zone scroller) --
// The player roams this half-box (world units) around screen centre before the
// camera scrolls; past an edge a tight lerp tracks that edge.
export const DEADZONE_HALF_X = 3
export const DEADZONE_HALF_Z = 2
export const CAMERA_LERP = 10
// Orthographic projection (no perspective/FOV distortion — a true flat side-on
// view). `zoom` is pixels per world unit at the canvas's pixel size; higher = more
// zoomed in. Tune to taste for the framing you want.
export const CAMERA_ZOOM = 48
