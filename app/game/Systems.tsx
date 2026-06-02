import { tickSystems } from '@blenjs/runtime-three'
import { useFrame } from '@react-three/fiber/webgpu'
import { useRef } from 'react'
import type { Object3D } from 'three'
import { registry, type TransformData } from '../components'
import { bulletStep, goalStep, shootStep } from '../systems'
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
      const p = (e.components.Transform as TransformData).pos
      o.position.set(p[0], p[1], p[2])
    }

    const player = ctx.player
    if (player) {
      const p = (player.components.Transform as TransformData).pos
      const cam = state.camera
      const k = Math.min(1, dt * 6)
      // Z-up world: follow the player on X, hold the camera back along -Y (depth),
      // and track height on Z with a small offset so we look slightly down.
      cam.position.x += (p[0] - cam.position.x) * k
      cam.position.y += (-16 - cam.position.y) * k
      cam.position.z += (p[2] + 2.5 - cam.position.z) * k
      cam.lookAt(p[0], 0, p[2])
    }
  })
  return null
}
