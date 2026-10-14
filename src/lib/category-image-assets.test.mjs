import { readFileSync } from 'node:fs'
import { it, expect } from 'vitest'
import { getAiCategoryImage } from './news.ts'

// Real file witness: a successful HTTP response alone can be an SPA HTML fallback.
it('resolves every category fallback to an actual checked-in WebP image', () => {
  for (const category of ['Hälsa','Miljö','Natur','Vetenskap','Kultur','Människor','Framsteg','Djur','unknown']) {
    for (const seed of ['','abc123','different article']) {
      const image = getAiCategoryImage(category, seed)
      const bytes = readFileSync(new URL('../../public' + image.url, import.meta.url))
      expect(bytes.subarray(0,4).toString()).toBe('RIFF')
      expect(bytes.subarray(8,12).toString()).toBe('WEBP')
      expect(image.caption).toContain('inte en dokumentation')
    }
  }
})
