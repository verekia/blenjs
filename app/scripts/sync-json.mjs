// Copies the source-of-truth root game.json into the app's public dir so the
// static export can fetch it at runtime. Run on predev/prebuild and by the watcher.
import { copyFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const src = resolve(here, '../../game.json')
const destDir = resolve(here, '../public')

mkdirSync(destDir, { recursive: true })
copyFileSync(src, resolve(destDir, 'game.json'))
console.log('synced game.json -> app/public/game.json')
