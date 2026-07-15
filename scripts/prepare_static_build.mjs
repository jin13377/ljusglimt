import { copyFile, mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const output = resolve(root, 'dist', 'data')
const files = ['news.json', 'seed-news.json']

await mkdir(output, { recursive: true })
await Promise.all(files.map((file) => copyFile(resolve(root, 'data', file), resolve(output, file))))

console.log(`Static news data copied to ${output}`)
