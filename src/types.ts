export type NewsOrigin = 'demo' | 'fetched'
export type NewsImageKind = 'source' | 'ai'

export interface NewsImage {
  kind: NewsImageKind
  url: string
  alt: string
  caption: string
  width: number
  height: number
  credit?: string
  rightsUrl?: string
}

export interface RawFetchedNews {
  id: string
  title: string
  url: string
  source: string
  language?: string
  published_at?: string
  source_excerpt?: string
  agent_summary?: string
  source_tier_bonus?: number
  positivity_score?: number
  positive_signals?: string[]
  source_image_verified?: boolean
  source_image_url?: string
  source_image_alt?: string
  source_image_credit?: string
  source_image_rights_url?: string
}

export interface RawSeedNews {
  id: string
  slug?: string
  title: string
  summary: string
  category?: string
  location?: string
  publishedAt?: string
  readTimeMinutes?: number
  featured?: boolean
  isDemo?: boolean
  source_image_verified?: boolean
  source_image_url?: string
  source_image_alt?: string
  source_image_credit?: string
  source_image_rights_url?: string
  source: { name: string; url: string }
}

export interface NewsArticle {
  id: string
  slug: string
  title: string
  excerpt: string
  category: string
  location: string
  publishedAt: string
  readTime: number
  featured: boolean
  source: string
  url: string
  origin: NewsOrigin
  language: string
  excerptLanguage: string
  hasAgentSummary: boolean
  score: number
  signals: string[]
  image: NewsImage
}

export interface User {
  id: string
  email: string
  name: string
  avatarUrl?: string | null
  role: string
}

export interface ForumSection {
  id: string
  title: string
  description: string
  icon: string
  topicCount?: number
  postCount?: number
  groupId?: string
  groupTitle?: string
  latest?: ForumLatest | null
}

export interface ForumLatest {
  id: string
  title: string
  author: string
  createdAt: string
  sectionId?: string
  sectionTitle?: string
}

export interface ForumGroup {
  id: string
  title: string
  description: string
  sections: ForumSection[]
}

export interface ForumTopicSummary {
  id: string
  title: string
  body: string
  author: string
  avatarUrl?: string | null
  createdAt: string
  lastActivity: string
  status: string
  replyCount: number
  views: number
  pinned: boolean
  locked: boolean
  followed: boolean
}

export interface ForumAuthor {
  name: string
  avatarUrl?: string | null
  memberSince?: string | null
  role?: string
}

export interface ForumReply {
  id: string
  body: string
  createdAt: string
  status: string
  author: ForumAuthor
}

export interface ForumTopic extends Omit<ForumTopicSummary, 'author' | 'replyCount' | 'avatarUrl'> {
  author: ForumAuthor
  replies: ForumReply[]
}

export interface SavedArticle {
  article_id: string
  title: string
  summary: string
  source: string
  url: string
  image?: string
  saved_at: string
}
