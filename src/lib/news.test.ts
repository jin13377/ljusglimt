import { describe, expect, it } from 'vitest'
import { inferCategory, normalizeFetched, normalizeSeed } from './news'

describe('news normalizer', () => {
  it('infers a category without relying on missing API fields', () => {
    expect(inferCategory({ id: '1', title: 'New solar energy record', url: 'https://example.com', source: 'Test' })).toBe('Miljö')
  })

  it('marks fetched items as fetched and uses source excerpts', () => {
    const item = normalizeFetched({ id: 'abc123', title: 'A hopeful study', url: 'https://example.com', source: 'NASA', source_excerpt: 'Useful context.' })
    expect(item.origin).toBe('fetched')
    expect(item.excerpt).toBe('Useful context.')
  })

  it('preserves demo source transparency', () => {
    const item = normalizeSeed({ id: 'demo', title: 'En ljus nyhet', summary: 'Sammanfattning', source: { name: 'WHO', url: 'https://who.int' } })
    expect(item.origin).toBe('demo')
    expect(item.source).toBe('WHO')
  })
})
