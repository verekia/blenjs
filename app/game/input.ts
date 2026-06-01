import { useEffect } from 'react'
import { getGame, setGame } from './store'
import type { Input } from './types'

const KEY_MAP: Record<string, keyof Input> = {
  ArrowLeft: 'left',
  KeyA: 'left',
  ArrowRight: 'right',
  KeyD: 'right',
  ArrowUp: 'jump',
  KeyW: 'jump',
  Space: 'jump',
  KeyJ: 'shoot',
  KeyF: 'shoot',
}

const setInput = (patch: Partial<Input>) => setGame({ input: { ...getGame().input, ...patch } })

/** Keyboard (+ click to shoot) input, written into the store as held booleans. */
export const useInput = (onRestart: () => void) => {
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.repeat) return
      if (e.code === 'KeyR') {
        onRestart()
        return
      }
      const key = KEY_MAP[e.code]
      if (key) {
        setInput({ [key]: true })
        if (e.code === 'Space') e.preventDefault()
      }
    }
    const up = (e: KeyboardEvent) => {
      const key = KEY_MAP[e.code]
      if (key) setInput({ [key]: false })
    }
    const shootDown = () => setInput({ shoot: true })
    const shootUp = () => setInput({ shoot: false })

    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    window.addEventListener('pointerdown', shootDown)
    window.addEventListener('pointerup', shootUp)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
      window.removeEventListener('pointerdown', shootDown)
      window.removeEventListener('pointerup', shootUp)
    }
  }, [onRestart])
}
