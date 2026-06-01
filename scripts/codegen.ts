import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { writeSchema } from '@blenjs/codegen'
import { registry } from '../app/components'

/**
 * One-shot codegen CLI. Reads the application registry and emits the committed
 * `generated/components.schema.json` that Blender's Python reads off disk.
 *
 *   bun run codegen
 */
const here = dirname(fileURLToPath(import.meta.url))
const out = resolve(here, '../generated/components.schema.json')
const doc = writeSchema(registry, out)

console.log(`✓ wrote ${out}`)
console.log(
  `  schemaVersion ${doc.schemaVersion} · ${doc.components.length} components: ` +
    doc.components.map(c => c.name).join(', '),
)
