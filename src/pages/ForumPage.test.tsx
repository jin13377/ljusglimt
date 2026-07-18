import { describe, expect, it } from 'vitest'
import { forumRoleLabel } from './ForumPage'

describe('forumRoleLabel', () => {
  it('does not describe existing seeded posts as AI posts', () => {
    expect(forumRoleLabel('ai')).toBe('Ljusglimt')
  })
})
