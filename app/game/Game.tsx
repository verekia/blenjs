import { Level } from '@blenjs/runtime-r3f'
import { Canvas } from '@react-three/fiber/webgpu'
import { useCallback, useEffect, useState } from 'react'
import { Object3D } from 'three'
import { Bullets } from './Bullets'
import { fetchAndHydrate, hydrateFromYaml } from './context'
import { HUD } from './HUD'
import { useInput } from './input'
import { renderEntity } from './Level'
import { useGame } from './store'
import { GameSystems } from './Systems'

// The world is Z-up right-handed (same frame as Blender / game.yaml): X right,
// Y depth, Z up. three.js has no hardcoded world up — it only reads `Object3D.up`
// for `lookAt()` and controls — so we point the default up at +Z before any
// camera is created. The renderer is unaffected; only orientation math is.
// (glTF models are Y-up by spec: wrap them in a group with rotation.x = +90° to
// lift them into this Z-up world when model loading is added.)
Object3D.DEFAULT_UP.set(0, 0, 1)

const World = () => {
  const order = useGame(s => s.order)
  const entities = useGame(s => s.entities)
  const list = order.map(id => entities[id]).filter(Boolean)
  return (
    <>
      <Level entities={list} renderEntity={renderEntity} />
      <Bullets />
      <GameSystems />
    </>
  )
}

export const Game = () => {
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setReady(false)
    setError(null)
    fetchAndHydrate('/game.yaml')
      .then(() => setReady(true))
      .catch(e => setError(String(e?.message ?? e)))
  }, [])

  useEffect(() => load(), [load])
  useInput(load) // R restarts by reloading the scene

  // Dev loop (spec §7 / §10.7): poll the synced YAML so "save in Blender ->
  // game reloads" works. The watcher copies game.yaml into public on change.
  useEffect(() => {
    if (process.env.NODE_ENV !== 'development') return
    let last: string | null = null
    const id = setInterval(async () => {
      try {
        const text = await (await fetch('/game.yaml', { cache: 'no-store' })).text()
        if (last !== null && text !== last) hydrateFromYaml(text)
        last = text
      } catch {
        // ignore transient fetch errors during dev
      }
    }, 1500)
    return () => clearInterval(id)
  }, [])

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
