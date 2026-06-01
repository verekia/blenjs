import { spawnSync } from 'node:child_process'
import { copyFileSync, mkdirSync, watch } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * Dev-loop glue (spec §10.7): regenerate the schema when the registry changes, and
 * mirror game.yaml into the app's public dir on save so the running dev server's
 * client poll reloads the level — i.e. "save in Blender -> game reloads".
 *
 * Run alongside the dev server:  bun run watch   (in one terminal)
 *                                bun run dev     (in another)
 */
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const gameYaml = resolve(root, 'game.yaml')
const publicDir = resolve(root, 'app/public')

const syncYaml = () => {
  try {
    mkdirSync(publicDir, { recursive: true })
    copyFileSync(gameYaml, resolve(publicDir, 'game.yaml'))
    console.log('• synced game.yaml -> app/public/game.yaml')
  } catch (e) {
    console.warn('  (game.yaml not found yet)', String(e))
  }
}

const runCodegen = () => {
  console.log('• registry changed -> running codegen')
  spawnSync('bun', ['run', 'codegen'], { cwd: root, stdio: 'inherit' })
}

let codegenTimer: ReturnType<typeof setTimeout> | undefined
let syncTimer: ReturnType<typeof setTimeout> | undefined
const debounce = (which: 'codegen' | 'sync') => {
  if (which === 'codegen') {
    clearTimeout(codegenTimer)
    codegenTimer = setTimeout(runCodegen, 150)
  } else {
    clearTimeout(syncTimer)
    syncTimer = setTimeout(syncYaml, 100)
  }
}

// Initial pass.
runCodegen()
syncYaml()

// Registry / library sources -> codegen.
for (const target of ['app/components.ts', 'app/systems', 'packages/core/src', 'packages/codegen/src']) {
  try {
    watch(resolve(root, target), { recursive: true }, () => debounce('codegen'))
  } catch {
    // non-recursive fallback for single files
    watch(resolve(root, target), () => debounce('codegen'))
  }
}

// Source-of-truth YAML -> public (the dev client polls /game.yaml).
watch(gameYaml, () => debounce('sync'))

console.log('blenjs watch running. Ctrl+C to stop.')
