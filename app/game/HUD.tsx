import { useGame } from './store'

/** React HUD reading Zustand — score, ammo, controls, and the win/lose banner. */
export const HUD = () => {
  const score = useGame(s => s.score)
  const ammo = useGame(s => s.ammo)
  const win = useGame(s => s.win)
  const lose = useGame(s => s.lose)

  return (
    <>
      <div className="pointer-events-none fixed top-4 left-4 flex flex-col gap-1 font-mono text-sm">
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
      </div>

      {(win || lose) && (
        <div
          className="fixed inset-0 flex items-center justify-center bg-black/60"
          style={{ animation: 'blenjs-pop 0.2s ease-out' }}
        >
          <div className="text-center">
            <div className={`text-5xl font-bold ${win ? 'text-emerald-400' : 'text-red-400'}`}>
              {win ? 'You win!' : 'You fell…'}
            </div>
            <div className="mt-3 text-white/70">
              Final score: <span className="tabular-nums">{score}</span>
            </div>
            <div className="mt-1 text-sm text-white/50">Press R to restart</div>
          </div>
        </div>
      )}
    </>
  )
}
