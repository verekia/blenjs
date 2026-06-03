import { useGame } from './store'

/**
 * React HUD reading Zustand — current level, score, ammo, and controls. Ending a
 * run (win/lose) is handled by the React screen flow in Game.tsx, so there is no
 * win/lose banner here.
 */
export const HUD = ({ level, levelCount }: { level: number; levelCount: number }) => {
  const score = useGame(s => s.score)
  const ammo = useGame(s => s.ammo)

  return (
    <>
      <div className="pointer-events-none fixed top-4 left-4 flex flex-col gap-1 font-mono text-sm">
        <div>
          Level <span className="tabular-nums">{level}</span> / <span className="tabular-nums">{levelCount}</span>
        </div>
        <div>
          Score: <span className="tabular-nums">{score}</span>
        </div>
        <div>
          Ammo: <span className="tabular-nums">{ammo}</span>
        </div>
      </div>

      <div className="pointer-events-none fixed top-4 right-4 text-right font-mono text-xs text-white/45">
        <div>← → / A D &nbsp;move</div>
        <div>Space / W &nbsp;jump</div>
        <div>F / J / click &nbsp;shoot</div>
        <div>R &nbsp;restart level</div>
      </div>
    </>
  )
}
