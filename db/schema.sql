-- Framtida portabel produktionsmodell. Den körbara lokala SQLite-modellen
-- skapas och migreras av init_db() i server.py.
PRAGMA foreign_keys = ON;

CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email_normalized TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'moderator', 'admin')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
  email_verified_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE forum_content (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('thread', 'reply')),
  parent_thread_id TEXT REFERENCES forum_content(id),
  author_id TEXT NOT NULL REFERENCES users(id),
  title TEXT,
  body TEXT NOT NULL,
  category TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'published', 'rejected', 'hidden')),
  created_at TEXT NOT NULL,
  published_at TEXT,
  CHECK ((kind = 'thread' AND title IS NOT NULL AND parent_thread_id IS NULL)
      OR (kind = 'reply' AND title IS NULL AND parent_thread_id IS NOT NULL))
);

CREATE TABLE moderation_decisions (
  id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES forum_content(id),
  moderator_id TEXT NOT NULL REFERENCES users(id),
  decision TEXT NOT NULL CHECK (decision IN ('published', 'rejected', 'hidden')),
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE reports (
  id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES forum_content(id),
  reporter_id TEXT NOT NULL REFERENCES users(id),
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'dismissed')),
  created_at TEXT NOT NULL,
  UNIQUE (content_id, reporter_id)
);

CREATE INDEX idx_content_public ON forum_content(status, published_at);
CREATE INDEX idx_content_queue ON forum_content(status, created_at);
