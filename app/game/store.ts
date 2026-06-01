import type { Entity } from '@blenjs/core'
import { create } from 'zustand'
import { MAX_AMMO } from './constants'
import type { Bullet, Input } from './types'

/**
 * The game store. Follows the reference repo's Zustand-entities idiom: a plain
 * `create(() => state)` with non-reactive `getState` for systems and reactive
 * selectors for views. Systems mutate entity component data in place (read each
 * frame in useFrame); React re-renders only when collections (entities/bullets)
 * are replaced.
 *
 * `entities` is the designed world (hydrated from YAML) PLUS the runtime-spawned
 * player. `bullets`, `score`, `ammo`, `win`/`lose` are the emergent layer — code,
 * never authored in YAML (spec §4).
 */
export type GameState = {
  entities: Record<string, Entity>
  order: string[]
  bullets: Bullet[]
  nextBulletId: number
  score: number
  ammo: number
  win: boolean
  lose: boolean
  input: Input
}

export const defaultState: GameState = {
  entities: {},
  order: [],
  bullets: [],
  nextBulletId: 1,
  score: 0,
  ammo: MAX_AMMO,
  win: false,
  lose: false,
  input: { left: false, right: false, jump: false, shoot: false },
}

export const useGame = create<GameState>(() => structuredClone(defaultState))

export const getGame = useGame.getState
export const setGame = useGame.setState
export const resetGame = () => setGame(structuredClone(defaultState))

// Expose getState on window for debugging (architecture skill convention).
if (typeof window !== 'undefined') {
  ;(window as unknown as { getGame: typeof getGame }).getGame = getGame
}
