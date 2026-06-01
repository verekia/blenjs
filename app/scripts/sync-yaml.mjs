// Copies the source-of-truth root game.yaml into the app's public dir so the
// static export can fetch it at runtime. Run on predev/prebuild and by the watcher.
import { copyFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const src = resolve(here, '../../game.yaml')
const destDir = resolve(here, '../public')

mkdirSync(destDir, { recursive: true })
copyFileSync(src, resolve(destDir, 'game.yaml'))
console.log('synced game.yaml -> app/public/game.yaml')
