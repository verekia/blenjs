/**
 * Title screen — pure React/HTML, not a BlenJS scene. Shown before the first run
 * and again when a run ends; `result` tints the outcome line shown on return.
 */
export const MainMenu = ({ result, onPlay }: { result: 'win' | 'lose' | null; onPlay: () => void }) => (
  <div className="fixed inset-0 flex flex-col items-center justify-center gap-10 bg-[#0e1014] font-mono select-none">
    <div className="text-center" style={{ animation: 'blenjs-pop 0.25s ease-out' }}>
      <h1 className="text-6xl font-bold tracking-tight text-emerald-400">BlenJS Platformer</h1>
      <p className="mt-3 text-sm text-white/45">Reach the flag across two levels — mind the gaps.</p>
    </div>

    {result ? (
      <p className={`text-lg ${result === 'win' ? 'text-emerald-400' : 'text-red-400'}`}>
        {result === 'win' ? 'You cleared both levels! 🎉' : 'You fell…'}
      </p>
    ) : null}

    <button
      type="button"
      onClick={onPlay}
      className="rounded-md bg-emerald-400 px-12 py-3 text-lg font-bold text-black transition-transform hover:scale-105"
    >
      {result ? 'Play again' : 'Play'}
    </button>

    <p className="text-xs text-white/30">
      ← → / A D&nbsp;&nbsp;move&nbsp;&nbsp;·&nbsp;&nbsp;Space&nbsp;&nbsp;jump&nbsp;&nbsp;·&nbsp;&nbsp;F /
      J&nbsp;&nbsp;shoot
    </p>
  </div>
)
