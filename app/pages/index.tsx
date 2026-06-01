import dynamic from 'next/dynamic'

// The game touches WebGPU/`window`, so render it client-only (no SSR).
const Game = dynamic(() => import('../game/Game').then(m => m.Game), { ssr: false })

const HomePage = () => <Game />

export default HomePage
