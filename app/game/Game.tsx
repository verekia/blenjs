import { Level } from '@blenjs/runtime-r3f'
import type { RawGame } from '@blenjs/runtime-three'
import { Canvas } from '@react-three/fiber/webgpu'
import { Suspense, useCallback, useEffect, useState } from 'react'
import { Object3D } from 'three'
import gameData from '../../platformer.blen.json'
import { Bullets } from './Bullets'
import { CAMERA_ZOOM } from './constants'
import { hydrateGame } from './context'
import { HUD } from './HUD'
import { useInput } from './input'
import { renderEntity } from './Level'
import { MainMenu } from './MainMenu'
import { resetGame, useGame } from './store'
import { GameSystems } from './Systems'

// The world is Z-up right-handed (same frame as Blender / .blen.json): X right,
// Y depth, Z up. three.js has no hardcoded world up — it only reads `Object3D.up`
// for `lookAt()` and controls — so we point the default up at +Z before any
// camera is created. (Models are exported Z-up — `build_assets.py` uses
// export_yup=False — so loaded glTF drops straight into this Z-up world.)
Object3D.DEFAULT_UP.set(0, 0, 1)

// Ordered level scenes straight from the .blen.json. Clearing one advances to the
// next; clearing the last (or dying) drops back to the menu. The levels are BlenJS
// scenes (data); the menu and the flow around them are plain React.
const LEVELS = Object.keys((gameData as RawGame).scenes ?? {})

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

// The playfield: the WebGPU canvas + HUD. Mounted only while playing, and re-keyed
// per level so every level starts with a fresh camera centred on the spawn.
const GameView = ({ level, levelCount, onRestart }: { level: number; levelCount: number; onRestart: () => void }) => {
  useInput(onRestart) // R restarts the current level; also wires movement/jump/shoot keys
  return (
    <>
      <Canvas
        key={level}
        orthographic
        camera={{ position: [0, -16, 3], up: [0, 0, 1], zoom: CAMERA_ZOOM, near: 0.1, far: 1000 }}
        onCreated={({ camera }) => {
          camera.up.set(0, 0, 1)
          // Aim once straight along +Y, perpendicular to the XZ game plane; the follow
          // code only translates the camera after this (no pitch/yaw/roll).
          camera.lookAt(camera.position.x, 0, camera.position.z)
        }}
      >
        <World />
      </Canvas>
      <HUD level={level} levelCount={levelCount} />
    </>
  )
}

/**
 * Top-level screen flow — pure React, no BlenJS scene. menu → play → menu. Play
 * loads the first level; clearing a level advances to the next; clearing the last
 * level (win) or falling (lose) returns to the menu, carrying the outcome.
 */
export const Game = () => {
  const [screen, setScreen] = useState<'menu' | 'playing'>('menu')
  const [levelIdx, setLevelIdx] = useState(0)
  const [result, setResult] = useState<'win' | 'lose' | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Hydrate the store from a level scene. .blen.json is imported as a module, so
  // this is a synchronous swap — no fetch.
  const load = useCallback((idx: number): boolean => {
    try {
      hydrateGame(gameData as RawGame, LEVELS[idx])
      setError(null)
      return true
    } catch (e) {
      setError(String((e as { message?: string })?.message ?? e))
      return false
    }
  }, [])

  const startGame = useCallback(() => {
    setResult(null)
    setLevelIdx(0)
    if (load(0)) setScreen('playing')
  }, [load])

  // R reloads the current level in place (the input system maps R → restart).
  const restart = useCallback(() => {
    load(levelIdx)
  }, [load, levelIdx])

  // Run outcome, watched off the store. A cleared level advances; the final level
  // (win) or a fall (lose) ends the run. resetGame wipes win/lose so the menu — and
  // the next run — start from a clean state.
  const win = useGame(s => s.win)
  const lose = useGame(s => s.lose)
  useEffect(() => {
    if (screen !== 'playing') return
    if (lose) {
      resetGame()
      setResult('lose')
      setScreen('menu')
    } else if (win) {
      const next = levelIdx + 1
      if (next < LEVELS.length) {
        setLevelIdx(next)
        load(next)
      } else {
        resetGame()
        setResult('win')
        setScreen('menu')
      }
    }
  }, [win, lose, screen, levelIdx, load])

  return (
    <>
      {screen === 'menu' ? (
        <MainMenu result={result} onPlay={startGame} />
      ) : (
        <GameView level={levelIdx + 1} levelCount={LEVELS.length} onRestart={restart} />
      )}
      {error ? (
        <div className="fixed inset-0 flex items-center justify-center p-8">
          <pre className="max-w-2xl rounded bg-red-950/80 p-4 font-mono text-sm whitespace-pre-wrap text-red-200">
            {error}
          </pre>
        </div>
      ) : null}
    </>
  )
}
