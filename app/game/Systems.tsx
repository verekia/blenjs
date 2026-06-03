import { tickSystems } from '@blenjs/runtime-three'
import { useFrame } from '@react-three/fiber/webgpu'
import { useRef } from 'react'
import type { Object3D } from 'three'
import { registry, type TransformData } from '../components'
import { bulletStep, goalStep, shootStep } from '../systems'
import { CAMERA_LERP, DEADZONE_HALF_X, DEADZONE_HALF_Z } from './constants'
import { makeContext } from './context'
import { getGame } from './store'

/**
 * The single frame-loop driver (spec §7.5). Per frame, in order:
 *   1. build the context from the store
 *   2. tick registry behavior systems (player/patrol/pickup) + runtime systems
 *      (shoot/bullets/goal) — frozen on win/lose
 *   3. sync logical Transforms onto captured Three.js objects
 *   4. follow the player with the camera
 */
export const GameSystems = () => {
  const elapsed = useRef(0)
  useFrame((state, delta) => {
    const dt = Math.min(delta, 0.05) // clamp big frames (tab switches) to avoid tunneling
    elapsed.current += dt
    const ctx = makeContext(dt, elapsed.current)

    const s = getGame()
    if (!s.win && !s.lose) {
      tickSystems(registry, ctx, dt)
      shootStep(dt, ctx)
      bulletStep(dt, ctx)
      goalStep(dt, ctx)
    }

    for (const e of ctx.entities) {
      const o = e.three as Object3D | undefined
      if (!o) continue
      const tr = e.components.Transform as TransformData
      o.position.set(tr.pos[0], tr.pos[1], tr.pos[2])
      o.rotation.set(tr.rot[0], tr.rot[1], tr.rot[2])
    }

    const player = ctx.player
    if (player) {
      const p = (player.components.Transform as TransformData).pos
      const cam = state.camera
      // Classic dead-zone scroller. The camera holds still while the player roams a
      // centred box; once the player pushes past an edge, a tight lerp tracks that
      // edge. Orientation is locked orthogonal to the XZ plane (aimed once in
      // Game.tsx) — only X and Z translate, depth (Y) is fixed — so the view never
      // pitches, yaws, or rolls.
      const k = Math.min(1, dt * CAMERA_LERP)
      const dx = p[0] - cam.position.x
      if (dx > DEADZONE_HALF_X) cam.position.x += (dx - DEADZONE_HALF_X) * k
      else if (dx < -DEADZONE_HALF_X) cam.position.x += (dx + DEADZONE_HALF_X) * k
      const dz = p[2] - cam.position.z
      if (dz > DEADZONE_HALF_Z) cam.position.z += (dz - DEADZONE_HALF_Z) * k
      else if (dz < -DEADZONE_HALF_Z) cam.position.z += (dz + DEADZONE_HALF_Z) * k
    }
  })
  return null
}
