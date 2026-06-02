import { spawnSync } from 'node:child_process'
import { watch } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * Dev-loop glue (spec §10.7): regenerate the schema when the component registry
 * changes, so Blender's UI and the runtime stay in sync while you edit components.
 *
 * game.json needs no watching here: the app imports it as a module, so saving it
 * (or saving from Blender) is picked up by the dev server's Fast Refresh directly.
 *
 * Run alongside the dev server:  bun run watch   (in one terminal)
 *                                bun run dev     (in another)
 */
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

const runCodegen = () => {
  console.log('• registry changed -> running codegen')
  spawnSync('bun', ['run', 'codegen'], { cwd: root, stdio: 'inherit' })
}

let codegenTimer: ReturnType<typeof setTimeout> | undefined
const debounce = () => {
  clearTimeout(codegenTimer)
  codegenTimer = setTimeout(runCodegen, 150)
}

// Initial pass.
runCodegen()

// Registry / library sources -> codegen.
for (const target of ['app/components.ts', 'app/systems', 'packages/core/src', 'packages/codegen/src']) {
  try {
    watch(resolve(root, target), { recursive: true }, debounce)
  } catch {
    // non-recursive fallback for single files
    watch(resolve(root, target), debounce)
  }
}

console.log('blenjs watch running. Ctrl+C to stop.')
