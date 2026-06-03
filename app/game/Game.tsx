import { Level } from '@blenjs/runtime-r3f'
import type { RawGame } from '@blenjs/runtime-three'
import { Canvas } from '@react-three/fiber/webgpu'
import { Suspense, useCallback, useEffect, useState } from 'react'
import { Object3D } from 'three'
import gameData from '../../game.json'
import { Bullets } from './Bullets'
import { hydrateGame } from './context'
import { HUD } from './HUD'
import { useInput } from './input'
import { renderEntity } from './Level'
import { useGame } from './store'
import { GameSystems } from './Systems'

// The world is Z-up right-handed (same frame as Blender / game.json): X right,
// Y depth, Z up. three.js has no hardcoded world up — it only reads `Object3D.up`
// for `lookAt()` and controls — so we point the default up at +Z before any
// camera is created. The renderer is unaffected; only orientation math is.
// (Models are exported Z-up — `build_assets.py` uses export_yup=False — so loaded glTF
// drops straight into this Z-up world with no rotation correction.)
Object3D.DEFAULT_UP.set(0, 0, 1)

const World = () => {
  const order = useGame(s => s.order)
  const entities = useGame(s => s.entities)
  const list = order.map(id => entities[id]).filter(Boolean)
  return (
    <>
      {/* glTF materials are lit (PBR) — without lights they render black. The basic-material
          primitives (platforms, goal) are unaffected by these. */}
      <ambientLight intensity={0.9} />
      <directionalLight position={[6, -10, 12]} intensity={2} />
      {/* useGLTF suspends until each model loads; systems/bullets keep running outside. */}
      <Suspense fallback={null}>
        <Level entities={list} renderEntity={renderEntity} />
      </Suspense>
      <Bullets />
      <GameSystems />
    </>
  )
}

export const Game = () => {
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // game.json is imported as a module, so it's bundled (no runtime fetch) and the
  // dev loop is just Fast Refresh: editing game.json — or saving from Blender —
  // re-evaluates this module with a fresh `gameData`. Keying `load` on it rebuilds
  // the callback, which re-fires the effect below and reloads the level.
  const load = useCallback(() => {
    try {
      hydrateGame(gameData as RawGame)
      setError(null)
      setReady(true)
    } catch (e) {
      setReady(false)
      setError(String((e as { message?: string })?.message ?? e))
    }
  }, [gameData])

  useEffect(() => load(), [load])
  useInput(load) // R restarts by reloading the scene

  return (
    <>
      <Canvas
        camera={{ position: [0, -16, 4], up: [0, 0, 1], fov: 55 }}
        onCreated={({ camera }) => camera.up.set(0, 0, 1)}
      >
        {ready && <World />}
      </Canvas>
      {error && (
        <div className="fixed inset-0 flex items-center justify-center p-8">
          <pre className="max-w-2xl rounded bg-red-950/80 p-4 font-mono text-sm whitespace-pre-wrap text-red-200">
            {error}
          </pre>
        </div>
      )}
      <HUD />
    </>
  )
}
