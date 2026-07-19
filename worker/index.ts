interface D1Result<T = unknown> {
  results?: T[]
  meta?: { changes?: number }
}

interface D1PreparedStatement {
  bind(...values: unknown[]): D1PreparedStatement
  first<T = Record<string, unknown>>(): Promise<T | null>
  all<T = Record<string, unknown>>(): Promise<D1Result<T>>
  run<T = Record<string, unknown>>(): Promise<D1Result<T>>
}

interface D1Database {
  prepare(query: string): D1PreparedStatement
  exec(query: string): Promise<unknown>
}

interface Env {
  DB: D1Database
  ASSETS: { fetch(request: Request): Promise<Response> }
  GOOGLE_CLIENT_ID?: string
}

interface SessionUser {
  id: string
  email: string
  name: string
  avatarUrl: string | null
  role: string
}

interface SeedTopic {
  id: string
  sectionId: string
  title: string
  body: string
  createdAt: string
  pinned?: boolean
  locked?: boolean
  views?: number
  replies?: Array<{ id: string; body: string; createdAt: string }>
}

interface GoogleIdTokenClaims {
  aud: string | string[]
  email: string
  email_verified: boolean
  exp: number
  iat?: number
  iss: string
  name?: string
  nbf?: number
  picture?: string
  sub: string
}

interface GoogleJwk extends JsonWebKey {
  kid?: string
}

const SESSION_COOKIE = 'glimt_session'
const SESSION_SECONDS = 60 * 60 * 24 * 30
const encoder = new TextEncoder()
const GOOGLE_CERTS_URL = 'https://www.googleapis.com/oauth2/v3/certs'
const GOOGLE_ISSUERS = new Set(['accounts.google.com', 'https://accounts.google.com'])
const PROFILE_AVATARS = new Set([
  '/profile-icons/sol.svg', '/profile-icons/katt.svg', '/profile-icons/hund.svg', '/profile-icons/hjarta.svg',
  '/profile-icons/blomma.svg', '/profile-icons/regnbage.svg', '/profile-icons/stjarna.svg', '/profile-icons/bi.svg',
])

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS app_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  avatar_url TEXT,
  role TEXT NOT NULL DEFAULT 'member',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
CREATE TABLE IF NOT EXISTS saved_articles (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  article_id TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  source TEXT NOT NULL,
  url TEXT NOT NULL,
  image TEXT NOT NULL DEFAULT '',
  saved_at TEXT NOT NULL,
  PRIMARY KEY (user_id, article_id)
);
CREATE TABLE IF NOT EXISTS forum_groups (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  sort_order INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS forum_sections (
  id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL REFERENCES forum_groups(id),
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  icon TEXT NOT NULL,
  sort_order INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS forum_topics (
  id TEXT PRIMARY KEY,
  section_id TEXT NOT NULL REFERENCES forum_sections(id),
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  author_name TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'published',
  created_at TEXT NOT NULL,
  last_activity TEXT NOT NULL,
  views INTEGER NOT NULL DEFAULT 0,
  pinned INTEGER NOT NULL DEFAULT 0,
  locked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_topics_section_activity ON forum_topics(section_id, last_activity DESC);
CREATE TABLE IF NOT EXISTS forum_replies (
  id TEXT PRIMARY KEY,
  topic_id TEXT NOT NULL REFERENCES forum_topics(id) ON DELETE CASCADE,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  author_name TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'published',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_replies_topic_time ON forum_replies(topic_id, created_at);
CREATE TABLE IF NOT EXISTS forum_reports (
  id TEXT PRIMARY KEY,
  topic_id TEXT NOT NULL REFERENCES forum_topics(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS forum_follows (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  topic_id TEXT NOT NULL REFERENCES forum_topics(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, topic_id)
);
CREATE TABLE IF NOT EXISTS rate_limits (
  key TEXT PRIMARY KEY,
  last_at INTEGER NOT NULL
);
`

const GROUPS = [
  ['nyheter-framsteg', 'Nyheter & framsteg', 'Diskutera positiva nyheter, forskning och lösningar som gör skillnad.', 1],
  ['samhalle-vardag', 'Samhälle & vardag', 'Lokala initiativ, kultur och de små sakerna som gör vardagen bättre.', 2],
  ['gemenskap', 'Gemenskap & Ljusglimt', 'Lär känna andra medlemmar, dela idéer och hjälp oss utveckla Ljusglimt.', 3],
] as const

const SECTIONS = [
  ['dagens-nyheter', 'nyheter-framsteg', 'Dagens positiva nyheter', 'Tipsa, diskutera och följ upp dagens ljusglimtar.', '☀️', 1],
  ['miljo-klimat', 'nyheter-framsteg', 'Miljö & klimat', 'Lösningar för natur, energi och ett hållbart samhälle.', '🌱', 2],
  ['vetenskap-teknik', 'nyheter-framsteg', 'Vetenskap & teknik', 'Forskning och teknik som förbättrar människors liv.', '🔬', 3],
  ['halsa-liv', 'nyheter-framsteg', 'Hälsa & liv', 'Framsteg inom vård, folkhälsa och livskvalitet.', '❤️', 4],
  ['lokalt-engagemang', 'samhalle-vardag', 'Lokalt engagemang', 'Människor och föreningar som gör orten lite bättre.', '🏘️', 1],
  ['vardagsgladje', 'samhalle-vardag', 'Vardagsglädje', 'Små och stora händelser som gav dig energi.', '✨', 2],
  ['djur-djurvanner', 'samhalle-vardag', 'Djur & djurvänner', 'Glada djurnyheter, egna djur och människor som hjälper djur.', '🐾', 3],
  ['kultur-kreativitet', 'samhalle-vardag', 'Kultur & kreativitet', 'Böcker, musik, spel, konst och egna projekt.', '🎨', 4],
  ['presentationer', 'gemenskap', 'Presentationer', 'Ny här? Säg hej och berätta vad du gärna läser om.', '👋', 1],
  ['goda-ideer', 'gemenskap', 'Goda idéer', 'Idéer och samarbeten som kan skapa fler ljusglimtar.', '💡', 2],
  ['sajtsnack', 'gemenskap', 'Om Ljusglimt', 'Frågor, förslag och information om sajten och forumet.', '🧭', 3],
] as const

const SEED_TOPICS: SeedTopic[] = [
  {
    id: 'topic-dagens-positiva', sectionId: 'dagens-nyheter', title: 'Vilken positiv nyhet borde fler känna till?',
    body: 'Dela en aktuell positiv nyhet som du tycker förtjänar mer uppmärksamhet. Skriv en kort sammanfattning och länka alltid till originalkällan.',
    createdAt: '2026-07-14T10:15:00+02:00', pinned: true, views: 42,
    replies: [{ id: 'reply-dagens-1', body: 'Jag fastnade för nyheten om fler återställda våtmarker. Det är konkret naturvård som hjälper både arter och klimat.', createdAt: '2026-07-14T11:02:00+02:00' }],
  },
  {
    id: 'topic-miljolosningar', sectionId: 'miljo-klimat', title: 'Smarta miljölösningar som redan fungerar',
    body: 'Här samlar vi exempel på natur- och klimatlösningar som har gett mätbara resultat. Berätta gärna var lösningen används och länka till en trovärdig källa.',
    createdAt: '2026-07-13T14:10:00+02:00', views: 31,
  },
  {
    id: 'topic-vetenskapshopp', sectionId: 'vetenskap-teknik', title: 'Forskning som ger hopp just nu',
    body: 'Tipsa om en ny upptäckt eller teknisk lösning som kan förbättra människors liv. Förklara den enkelt och länka helst till universitetet, studien eller en etablerad vetenskapskälla.',
    createdAt: '2026-07-12T18:40:00+02:00', views: 27,
  },
  {
    id: 'topic-halsaframsteg', sectionId: 'halsa-liv', title: 'Små och stora framsteg inom hälsa',
    body: 'Dela verifierade framsteg inom vård, omsorg, folkhälsa och livskvalitet. Forumet ersätter inte medicinsk rådgivning, så håll diskussionen allmän och källbaserad.',
    createdAt: '2026-07-11T09:25:00+02:00', views: 19,
  },
  {
    id: 'topic-lokala-initiativ', sectionId: 'lokalt-engagemang', title: 'Tipsa om ett positivt initiativ där du bor',
    body: 'Känner du till en förening, person eller idé som förbättrar ditt område? Tipsa oss och länka gärna till en verifierbar källa.',
    createdAt: '2026-07-13T16:20:00+02:00', views: 24,
  },
  {
    id: 'topic-vardagsgladje', sectionId: 'vardagsgladje', title: 'Vad gjorde dig glad i dag?',
    body: 'Dela en liten eller stor sak som gav dig energi i dag. Håll tonen varm, konkret och respektfull.',
    createdAt: '2026-07-14T07:30:00+02:00', views: 38,
    replies: [{ id: 'reply-vardag-1', body: 'En granne hjälpte mig bära upp matkassarna utan att jag behövde fråga.', createdAt: '2026-07-14T08:05:00+02:00' }],
  },
  {
    id: 'topic-kulturgladje', sectionId: 'kultur-kreativitet', title: 'Vad har inspirerat dig den här veckan?',
    body: 'Tipsa om en bok, låt, film, ett spel, konstverk eller eget projekt som har gett dig energi. Berätta gärna varför, utan att avslöja för mycket av handlingen.',
    createdAt: '2026-07-10T19:30:00+02:00', views: 36,
    replies: [{ id: 'reply-kultur-1', body: 'Jag gick på en liten gratiskonsert i parken. Att se så många generationer samlas gjorde hela veckan bättre.', createdAt: '2026-07-11T08:12:00+02:00' }],
  },
  {
    id: 'topic-presentera-dig', sectionId: 'presentationer', title: 'Ny på Ljusglimt? Presentera dig här',
    body: 'Välkommen! Berätta gärna vad du heter eller vill kallas, vilket ämne du är mest nyfiken på och vilken sorts positiva nyheter du gärna läser. Dela inga privata kontaktuppgifter.',
    createdAt: '2026-07-09T12:00:00+02:00', pinned: true, views: 64,
  },
  {
    id: 'topic-ideverkstad', sectionId: 'goda-ideer', title: 'Idéverkstad: något gott vi kan göra tillsammans',
    body: 'Har du en enkel idé som kan göra skolan, jobbet, kvarteret eller nätet lite bättre? Beskriv problemet, idén och ett första litet steg som går att testa.',
    createdAt: '2026-07-08T15:45:00+02:00', views: 48,
  },
  {
    id: 'topic-forumregler', sectionId: 'sajtsnack', title: 'Välkommen – så håller vi forumet vänligt',
    body: 'Var vänlig och saklig, skydda personuppgifter och länka källa vid faktapåståenden. Rapportera innehåll som behöver granskas i stället för att gå till personangrepp.',
    createdAt: '2026-07-07T08:00:00+02:00', pinned: true, locked: true, views: 88,
  },
]

let schemaPromise: Promise<void> | undefined
let googleKeysCache: { expiresAt: number; keys: GoogleJwk[] } | undefined

function nowIso() {
  return new Date().toISOString()
}

function json(data: unknown, status = 200, headers: HeadersInit = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...headers },
  })
}

function clean(value: unknown, maxLength: number) {
  return typeof value === 'string' ? value.trim().replace(/\r\n/g, '\n').slice(0, maxLength) : ''
}

function isEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

function linkCount(value: string) {
  return (value.match(/https?:\/\//gi) || []).length
}

function parseCookies(request: Request) {
  const cookies = new Map<string, string>()
  for (const part of (request.headers.get('cookie') || '').split(';')) {
    const index = part.indexOf('=')
    if (index > 0) cookies.set(part.slice(0, index).trim(), decodeURIComponent(part.slice(index + 1).trim()))
  }
  return cookies
}

function bytesToBase64Url(bytes: Uint8Array) {
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function base64UrlToBytes(value: string) {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4)
  const binary = atob(base64)
  return Uint8Array.from(binary, (character) => character.charCodeAt(0))
}

async function sha256(value: string) {
  const digest = await crypto.subtle.digest('SHA-256', encoder.encode(value))
  return bytesToBase64Url(new Uint8Array(digest))
}

async function passwordHash(password: string) {
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const key = await crypto.subtle.importKey('raw', encoder.encode(password), 'PBKDF2', false, ['deriveBits'])
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations: 210_000 }, key, 256)
  return `pbkdf2$210000$${bytesToBase64Url(salt)}$${bytesToBase64Url(new Uint8Array(bits))}`
}

async function verifyPassword(password: string, stored: string) {
  const [scheme, iterationsText, saltText, expectedText] = stored.split('$')
  if (scheme !== 'pbkdf2' || !iterationsText || !saltText || !expectedText) return false
  const iterations = Number(iterationsText)
  if (!Number.isInteger(iterations) || iterations < 100_000 || iterations > 1_000_000) return false
  const salt = base64UrlToBytes(saltText)
  const expected = base64UrlToBytes(expectedText)
  const key = await crypto.subtle.importKey('raw', encoder.encode(password), 'PBKDF2', false, ['deriveBits'])
  const bits = new Uint8Array(await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations }, key, expected.length * 8))
  if (bits.length !== expected.length) return false
  let difference = 0
  for (let index = 0; index < bits.length; index += 1) difference |= bits[index] ^ expected[index]
  return difference === 0
}

async function ensureDatabase(env: Env) {
  if (schemaPromise) return schemaPromise
  schemaPromise = (async () => {
    try {
      const marker = await env.DB.prepare("SELECT value FROM app_meta WHERE key = 'schema_version'").first<{ value: string }>()
      if (Number(marker?.value || 0) >= 4) return
    } catch {
      // The first request creates the schema below.
    }
    const schema = SCHEMA_SQL.split(';')
      .map((statement) => statement.replace(/\s+/g, ' ').trim())
      .filter(Boolean)
      .join(';\n') + ';'
    await env.DB.exec(schema)
    for (const group of GROUPS) {
      await env.DB.prepare('INSERT OR IGNORE INTO forum_groups (id, title, description, sort_order) VALUES (?, ?, ?, ?)').bind(...group).run()
    }
    for (const section of SECTIONS) {
      await env.DB.prepare('INSERT OR IGNORE INTO forum_sections (id, group_id, title, description, icon, sort_order) VALUES (?, ?, ?, ?, ?, ?)').bind(...section).run()
    }
    for (const topic of SEED_TOPICS) {
      await env.DB.prepare(`INSERT OR IGNORE INTO forum_topics
        (id, section_id, user_id, author_name, title, body, status, created_at, last_activity, views, pinned, locked)
        VALUES (?, ?, NULL, 'Ljusglimt', ?, ?, 'published', ?, ?, ?, ?, ?)`)
        .bind(topic.id, topic.sectionId, topic.title, topic.body, topic.createdAt, topic.replies?.at(-1)?.createdAt || topic.createdAt, topic.views || 0, topic.pinned ? 1 : 0, topic.locked ? 1 : 0).run()
      for (const reply of topic.replies || []) {
        await env.DB.prepare(`INSERT OR IGNORE INTO forum_replies
          (id, topic_id, user_id, author_name, body, status, created_at)
          VALUES (?, ?, NULL, 'Ljusglimt', ?, 'published', ?)`)
          .bind(reply.id, topic.id, reply.body, reply.createdAt).run()
      }
    }
    await env.DB.prepare("INSERT OR REPLACE INTO app_meta (key, value) VALUES ('schema_version', '1')").run()

    const columns = (await env.DB.prepare('PRAGMA table_info(users)').all<{ name: string }>()).results || []
    if (!columns.some((column) => column.name === 'google_sub')) {
      try {
        await env.DB.exec('ALTER TABLE users ADD COLUMN google_sub TEXT;')
      } catch (error) {
        const refreshed = (await env.DB.prepare('PRAGMA table_info(users)').all<{ name: string }>()).results || []
        if (!refreshed.some((column) => column.name === 'google_sub')) throw error
      }
    }
    await env.DB.exec('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub);')
    await env.DB.prepare("INSERT OR REPLACE INTO app_meta (key, value) VALUES ('schema_version', '2')").run()

    await env.DB.prepare("UPDATE forum_topics SET author_name = 'Ljusglimt' WHERE user_id IS NULL AND author_name = 'Ljusglimt AI'").run()
    await env.DB.prepare("UPDATE forum_replies SET author_name = 'Ljusglimt' WHERE user_id IS NULL AND author_name = 'Ljusglimt AI'").run()
    await env.DB.prepare("UPDATE forum_topics SET body = ? WHERE id = 'topic-forumregler'")
      .bind(SEED_TOPICS.find((topic) => topic.id === 'topic-forumregler')?.body || '').run()
    await env.DB.prepare("INSERT OR REPLACE INTO app_meta (key, value) VALUES ('schema_version', '3')").run()
    await env.DB.prepare("INSERT OR REPLACE INTO app_meta (key, value) VALUES ('schema_version', '4')").run()
  })().catch((error) => {
    schemaPromise = undefined
    throw error
  })
  return schemaPromise
}

function decodeJsonSegment<T>(segment: string): T {
  try {
    return JSON.parse(new TextDecoder().decode(base64UrlToBytes(segment))) as T
  } catch {
    throw new Error('Ogiltig Google-token.')
  }
}

function googleCacheSeconds(response: Response) {
  const match = response.headers.get('cache-control')?.match(/max-age=(\d+)/i)
  return Math.min(Math.max(Number(match?.[1] || 3_600), 300), 86_400)
}

async function googleSigningKeys(forceRefresh = false) {
  if (!forceRefresh && googleKeysCache && googleKeysCache.expiresAt > Date.now()) return googleKeysCache.keys
  const response = await fetch(GOOGLE_CERTS_URL, { headers: { accept: 'application/json' } })
  if (!response.ok) throw new Error('Google kunde inte verifieras just nu.')
  const body = await response.json() as { keys?: GoogleJwk[] }
  if (!Array.isArray(body.keys) || !body.keys.length) throw new Error('Google skickade inga verifieringsnycklar.')
  googleKeysCache = { keys: body.keys, expiresAt: Date.now() + googleCacheSeconds(response) * 1_000 }
  return body.keys
}

async function verifyGoogleIdToken(credential: string, clientId: string) {
  const parts = credential.split('.')
  if (parts.length !== 3 || credential.length > 12_000) throw new Error('Ogiltig Google-token.')
  const header = decodeJsonSegment<{ alg?: string; kid?: string; typ?: string }>(parts[0])
  if (header.alg !== 'RS256' || !header.kid) throw new Error('Google-token använder fel signering.')

  let keys = await googleSigningKeys()
  let jwk = keys.find((key) => key.kid === header.kid)
  if (!jwk) {
    keys = await googleSigningKeys(true)
    jwk = keys.find((key) => key.kid === header.kid)
  }
  if (!jwk) throw new Error('Google-token kunde inte verifieras.')

  const key = await crypto.subtle.importKey(
    'jwk',
    jwk,
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['verify'],
  )
  const validSignature = await crypto.subtle.verify(
    'RSASSA-PKCS1-v1_5',
    key,
    base64UrlToBytes(parts[2]),
    encoder.encode(`${parts[0]}.${parts[1]}`),
  )
  if (!validSignature) throw new Error('Google-token kunde inte verifieras.')

  const claims = decodeJsonSegment<GoogleIdTokenClaims>(parts[1])
  const now = Math.floor(Date.now() / 1_000)
  const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud]
  if (!audiences.includes(clientId)) throw new Error('Google-token är avsedd för en annan webbplats.')
  if (!GOOGLE_ISSUERS.has(claims.iss)) throw new Error('Google-token har fel utgivare.')
  if (!Number.isFinite(claims.exp) || claims.exp <= now - 60) throw new Error('Google-inloggningen har gått ut. Försök igen.')
  if (claims.nbf && claims.nbf > now + 60) throw new Error('Google-token är inte giltig ännu.')
  if (claims.iat && claims.iat > now + 300) throw new Error('Google-token har fel tid.')
  if (!claims.sub || !isEmail(claims.email) || claims.email_verified !== true) throw new Error('Google-kontots e-postadress är inte verifierad.')
  return claims
}

function safeGoogleAvatar(value: string | undefined) {
  if (!value) return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && (url.hostname === 'googleusercontent.com' || url.hostname.endsWith('.googleusercontent.com')) ? url.href : null
  } catch {
    return null
  }
}

async function readBody(request: Request) {
  const contentLength = Number(request.headers.get('content-length') || 0)
  if (contentLength > 30_000) throw new Response(JSON.stringify({ error: 'För mycket text skickades.' }), { status: 413, headers: { 'content-type': 'application/json' } })
  try {
    return await request.json() as Record<string, unknown>
  } catch {
    throw new Response(JSON.stringify({ error: 'Ogiltig förfrågan.' }), { status: 400, headers: { 'content-type': 'application/json' } })
  }
}

function assertSameOrigin(request: Request) {
  const origin = request.headers.get('origin')
  if (origin && origin !== new URL(request.url).origin) {
    throw new Response(JSON.stringify({ error: 'Förfrågan blockerades.' }), { status: 403, headers: { 'content-type': 'application/json' } })
  }
}

async function currentUser(env: Env, request: Request) {
  const token = parseCookies(request).get(SESSION_COOKIE)
  if (!token) return null
  const tokenHash = await sha256(token)
  const row = await env.DB.prepare(`SELECT u.id, u.email, u.name, u.avatar_url, u.role
    FROM sessions s JOIN users u ON u.id = s.user_id
    WHERE s.token_hash = ? AND s.expires_at > ?`).bind(tokenHash, Date.now()).first<{ id: string; email: string; name: string; avatar_url: string | null; role: string }>()
  return row ? { id: row.id, email: row.email, name: row.name, avatarUrl: row.avatar_url, role: row.role } satisfies SessionUser : null
}

async function requireUser(env: Env, request: Request) {
  const user = await currentUser(env, request)
  if (!user) throw json({ error: 'Logga in för att fortsätta.', code: 'AUTH_REQUIRED' }, 401)
  return user
}

async function createSession(env: Env, userId: string) {
  const raw = bytesToBase64Url(crypto.getRandomValues(new Uint8Array(32)))
  const expiresAt = Date.now() + SESSION_SECONDS * 1000
  await env.DB.prepare('DELETE FROM sessions WHERE expires_at <= ?').bind(Date.now()).run()
  await env.DB.prepare('INSERT INTO sessions (id, user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?, ?)')
    .bind(crypto.randomUUID(), userId, await sha256(raw), expiresAt, nowIso()).run()
  return `${SESSION_COOKIE}=${encodeURIComponent(raw)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${SESSION_SECONDS}`
}

function clearSessionCookie() {
  return `${SESSION_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`
}

async function rateLimit(env: Env, key: string, waitMs: number) {
  const now = Date.now()
  const result = await env.DB.prepare(`INSERT INTO rate_limits (key, last_at) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET last_at = excluded.last_at
    WHERE rate_limits.last_at <= ?`).bind(key, now, now - waitMs).run()
  return (result.meta?.changes || 0) > 0
}

function clientAddress(request: Request) {
  return request.headers.get('cf-connecting-ip') || 'local'
}

async function handleRegister(env: Env, request: Request) {
  const body = await readBody(request)
  const name = clean(body.name, 40)
  const email = clean(body.email, 160).toLocaleLowerCase('sv')
  const password = typeof body.password === 'string' ? body.password : ''
  if (name.length < 2) return json({ error: 'Namnet måste ha minst två tecken.' }, 400)
  if (!isEmail(email)) return json({ error: 'Skriv en giltig e-postadress.' }, 400)
  if (password.length < 8 || password.length > 128) return json({ error: 'Lösenordet måste ha minst åtta tecken.' }, 400)
  if (!await rateLimit(env, `register:${clientAddress(request)}`, 10_000)) return json({ error: 'Vänta en liten stund och försök igen.' }, 429)
  const exists = await env.DB.prepare('SELECT id FROM users WHERE email = ?').bind(email).first()
  if (exists) return json({ error: 'Det finns redan ett konto med den e-postadressen.' }, 409)
  const user: SessionUser = { id: crypto.randomUUID(), email, name, avatarUrl: null, role: 'member' }
  await env.DB.prepare('INSERT INTO users (id, email, name, password_hash, avatar_url, role, created_at) VALUES (?, ?, ?, ?, NULL, ?, ?)')
    .bind(user.id, email, name, await passwordHash(password), user.role, nowIso()).run()
  return json({ user }, 201, { 'set-cookie': await createSession(env, user.id) })
}

async function handleLogin(env: Env, request: Request) {
  const body = await readBody(request)
  const email = clean(body.email, 160).toLocaleLowerCase('sv')
  const password = typeof body.password === 'string' ? body.password : ''
  if (!await rateLimit(env, `login:${clientAddress(request)}`, 1_500)) return json({ error: 'Vänta en liten stund och försök igen.' }, 429)
  const row = await env.DB.prepare('SELECT id, email, name, password_hash, avatar_url, role FROM users WHERE email = ?').bind(email).first<{ id: string; email: string; name: string; password_hash: string; avatar_url: string | null; role: string }>()
  if (!row || !await verifyPassword(password, row.password_hash)) return json({ error: 'Fel e-postadress eller lösenord.' }, 401)
  const user: SessionUser = { id: row.id, email: row.email, name: row.name, avatarUrl: row.avatar_url, role: row.role }
  return json({ user }, 200, { 'set-cookie': await createSession(env, user.id) })
}

async function handleGoogleLogin(env: Env, request: Request) {
  if (!env.GOOGLE_CLIENT_ID) return json({ error: 'Google-inloggning är inte aktiverad ännu.' }, 501)
  if (!await rateLimit(env, `google:${clientAddress(request)}`, 1_500)) return json({ error: 'Vänta en liten stund och försök igen.' }, 429)
  const body = await readBody(request)
  const credential = typeof body.credential === 'string' ? body.credential : ''
  if (!credential) return json({ error: 'Google skickade ingen giltig inloggning.' }, 400)

  let claims: GoogleIdTokenClaims
  try {
    claims = await verifyGoogleIdToken(credential, env.GOOGLE_CLIENT_ID)
  } catch (error) {
    console.warn('Google identity verification failed', error)
    return json({ error: error instanceof Error ? error.message : 'Google-inloggningen kunde inte verifieras.' }, 401)
  }

  const email = claims.email.toLocaleLowerCase('sv')
  const avatarUrl = safeGoogleAvatar(claims.picture)
  let row = await env.DB.prepare('SELECT id, email, name, avatar_url, role FROM users WHERE google_sub = ?')
    .bind(claims.sub).first<{ id: string; email: string; name: string; avatar_url: string | null; role: string }>()

  if (!row) {
    const existing = await env.DB.prepare('SELECT id, email, name, avatar_url, role, google_sub FROM users WHERE email = ?')
      .bind(email).first<{ id: string; email: string; name: string; avatar_url: string | null; role: string; google_sub: string | null }>()
    if (existing?.google_sub && existing.google_sub !== claims.sub) {
      return json({ error: 'E-postadressen är redan kopplad till ett annat Google-konto.' }, 409)
    }
    if (existing) {
      await env.DB.prepare('UPDATE users SET google_sub = ?, avatar_url = COALESCE(avatar_url, ?) WHERE id = ?')
        .bind(claims.sub, avatarUrl, existing.id).run()
      row = { ...existing, avatar_url: existing.avatar_url || avatarUrl }
    } else {
      const id = crypto.randomUUID()
      const name = clean(claims.name, 40) || email.split('@')[0].slice(0, 40)
      await env.DB.prepare(`INSERT INTO users
        (id, email, name, password_hash, avatar_url, role, created_at, google_sub)
        VALUES (?, ?, ?, ?, ?, 'member', ?, ?)`)
        .bind(id, email, name, `google$disabled$${bytesToBase64Url(crypto.getRandomValues(new Uint8Array(24)))}`, avatarUrl, nowIso(), claims.sub).run()
      row = { id, email, name, avatar_url: avatarUrl, role: 'member' }
    }
  }

  const user: SessionUser = { id: row.id, email: row.email, name: row.name, avatarUrl: row.avatar_url, role: row.role }
  return json({ user }, 200, { 'set-cookie': await createSession(env, user.id) })
}

async function handleLogout(env: Env, request: Request) {
  const token = parseCookies(request).get(SESSION_COOKIE)
  if (token) await env.DB.prepare('DELETE FROM sessions WHERE token_hash = ?').bind(await sha256(token)).run()
  return json({ ok: true }, 200, { 'set-cookie': clearSessionCookie() })
}

async function sectionDetails(env: Env, sectionId: string) {
  return env.DB.prepare(`SELECT s.id, s.title, s.description, s.icon, s.group_id, g.title AS group_title
    FROM forum_sections s JOIN forum_groups g ON g.id = s.group_id WHERE s.id = ?`)
    .bind(sectionId).first<{ id: string; title: string; description: string; icon: string; group_id: string; group_title: string }>()
}

async function forumIndex(env: Env) {
  const groups = (await env.DB.prepare('SELECT id, title, description FROM forum_groups ORDER BY sort_order').all<{ id: string; title: string; description: string }>()).results || []
  const sections = (await env.DB.prepare(`SELECT s.id, s.group_id, s.title, s.description, s.icon,
      (SELECT COUNT(*) FROM forum_topics t WHERE t.section_id = s.id AND t.status = 'published') AS topic_count,
      (SELECT COUNT(*) FROM forum_topics t WHERE t.section_id = s.id AND t.status = 'published') +
      (SELECT COUNT(*) FROM forum_replies r JOIN forum_topics t ON t.id = r.topic_id WHERE t.section_id = s.id AND r.status = 'published') AS post_count
    FROM forum_sections s ORDER BY s.sort_order`).all<{ id: string; group_id: string; title: string; description: string; icon: string; topic_count: number; post_count: number }>()).results || []
  const latestRows = (await env.DB.prepare(`SELECT t.id, t.title, t.author_name, t.last_activity, t.section_id, s.title AS section_title
    FROM forum_topics t JOIN forum_sections s ON s.id = t.section_id WHERE t.status = 'published'
    ORDER BY t.last_activity DESC LIMIT 8`).all<{ id: string; title: string; author_name: string; last_activity: string; section_id: string; section_title: string }>()).results || []
  const sectionLatestRows = (await env.DB.prepare(`WITH ranked AS (
      SELECT t.id, t.title, t.author_name, t.last_activity, t.section_id, s.title AS section_title,
        ROW_NUMBER() OVER (PARTITION BY t.section_id ORDER BY t.last_activity DESC) AS position
      FROM forum_topics t JOIN forum_sections s ON s.id = t.section_id WHERE t.status = 'published'
    ) SELECT id, title, author_name, last_activity, section_id, section_title FROM ranked WHERE position = 1`)
    .all<{ id: string; title: string; author_name: string; last_activity: string; section_id: string; section_title: string }>()).results || []
  const latestBySection = new Map(sectionLatestRows.map((row) => [row.section_id, row]))
  const mappedGroups = groups.map((group) => ({
    id: group.id,
    title: group.title,
    description: group.description,
    sections: sections.filter((section) => section.group_id === group.id).map((section) => {
      const latest = latestBySection.get(section.id)
      return {
        id: section.id, title: section.title, description: section.description, icon: section.icon,
        topicCount: Number(section.topic_count), postCount: Number(section.post_count), groupId: group.id, groupTitle: group.title,
        latest: latest ? { id: latest.id, title: latest.title, author: latest.author_name, createdAt: latest.last_activity, sectionId: section.id, sectionTitle: section.title } : null,
      }
    }),
  }))
  const counts = await env.DB.prepare(`SELECT
    (SELECT COUNT(*) FROM forum_topics WHERE status = 'published') AS topics,
    (SELECT COUNT(*) FROM forum_topics WHERE status = 'published') + (SELECT COUNT(*) FROM forum_replies WHERE status = 'published') AS posts,
    (SELECT COUNT(*) FROM users) AS members`).first<{ topics: number; posts: number; members: number }>()
  return {
    groups: mappedGroups,
    latest: latestRows.map((row) => ({ id: row.id, title: row.title, author: row.author_name, createdAt: row.last_activity, sectionId: row.section_id, sectionTitle: row.section_title })),
    stats: { topics: Number(counts?.topics || 0), posts: Number(counts?.posts || 0), members: Number(counts?.members || 0) },
  }
}

async function forumTopics(env: Env, request: Request, sectionId: string) {
  const section = await sectionDetails(env, sectionId)
  if (!section) return json({ error: 'Avdelningen finns inte.' }, 404)
  const user = await currentUser(env, request)
  const rows = (await env.DB.prepare(`SELECT t.id, t.title, t.body, t.author_name, u.avatar_url, t.created_at, t.last_activity, t.status,
      (SELECT COUNT(*) FROM forum_replies r WHERE r.topic_id = t.id AND r.status = 'published') AS reply_count,
      t.views, t.pinned, t.locked,
      CASE WHEN f.user_id IS NULL THEN 0 ELSE 1 END AS followed
    FROM forum_topics t LEFT JOIN users u ON u.id = t.user_id
    LEFT JOIN forum_follows f ON f.topic_id = t.id AND f.user_id = ?
    WHERE t.section_id = ? AND t.status = 'published'
    ORDER BY t.pinned DESC, t.last_activity DESC`).bind(user?.id || '', sectionId).all<{ id: string; title: string; body: string; author_name: string; avatar_url: string | null; created_at: string; last_activity: string; status: string; reply_count: number; views: number; pinned: number; locked: number; followed: number }>()).results || []
  return json({
    section: { id: section.id, title: section.title, description: section.description, icon: section.icon, groupId: section.group_id, groupTitle: section.group_title },
    topics: rows.map((row) => ({ id: row.id, title: row.title, body: row.body, author: row.author_name, avatarUrl: row.avatar_url, createdAt: row.created_at, lastActivity: row.last_activity, status: row.status, replyCount: Number(row.reply_count), views: Number(row.views), pinned: Boolean(row.pinned), locked: Boolean(row.locked), followed: Boolean(row.followed) })),
  })
}

async function authorFor(env: Env, userId: string | null, authorName: string) {
  if (!userId) return { name: authorName, avatarUrl: null, memberSince: null, role: 'ai' }
  const user = await env.DB.prepare('SELECT name, avatar_url, created_at, role FROM users WHERE id = ?').bind(userId).first<{ name: string; avatar_url: string | null; created_at: string; role: string }>()
  return user ? { name: user.name, avatarUrl: user.avatar_url, memberSince: user.created_at, role: user.role } : { name: authorName, avatarUrl: null, memberSince: null, role: 'member' }
}

async function forumTopic(env: Env, request: Request, topicId: string) {
  const user = await currentUser(env, request)
  const row = await env.DB.prepare(`SELECT t.*, s.title AS section_title, s.description AS section_description, s.icon AS section_icon,
      s.group_id, g.title AS group_title, CASE WHEN f.user_id IS NULL THEN 0 ELSE 1 END AS followed
    FROM forum_topics t JOIN forum_sections s ON s.id = t.section_id JOIN forum_groups g ON g.id = s.group_id
    LEFT JOIN forum_follows f ON f.topic_id = t.id AND f.user_id = ?
    WHERE t.id = ? AND t.status = 'published'`).bind(user?.id || '', topicId).first<{ id: string; section_id: string; user_id: string | null; author_name: string; title: string; body: string; status: string; created_at: string; last_activity: string; views: number; pinned: number; locked: number; section_title: string; section_description: string; section_icon: string; group_id: string; group_title: string; followed: number }>()
  if (!row) return json({ error: 'Tråden finns inte.' }, 404)
  await env.DB.prepare('UPDATE forum_topics SET views = views + 1 WHERE id = ?').bind(topicId).run()
  const replies = (await env.DB.prepare(`SELECT id, user_id, author_name, body, status, created_at
    FROM forum_replies WHERE topic_id = ? AND status = 'published' ORDER BY created_at`).bind(topicId).all<{ id: string; user_id: string | null; author_name: string; body: string; status: string; created_at: string }>()).results || []
  const mappedReplies = await Promise.all(replies.map(async (reply) => ({ id: reply.id, body: reply.body, createdAt: reply.created_at, status: reply.status, author: await authorFor(env, reply.user_id, reply.author_name) })))
  return json({
    section: { id: row.section_id, title: row.section_title, description: row.section_description, icon: row.section_icon, groupId: row.group_id, groupTitle: row.group_title },
    topic: { id: row.id, title: row.title, body: row.body, author: await authorFor(env, row.user_id, row.author_name), createdAt: row.created_at, lastActivity: row.last_activity, status: row.status, replies: mappedReplies, views: Number(row.views) + 1, pinned: Boolean(row.pinned), locked: Boolean(row.locked), followed: Boolean(row.followed) },
  })
}

async function createTopic(env: Env, request: Request) {
  const user = await requireUser(env, request)
  const body = await readBody(request)
  const sectionId = clean(body.sectionId, 80)
  const title = clean(body.title, 100)
  const text = clean(body.body, 2_000)
  if (title.length < 5 || text.length < 10) return json({ error: 'Skriv en tydlig rubrik och minst tio tecken i inlägget.' }, 400)
  if (linkCount(text) > 3) return json({ error: 'Ett inlägg kan innehålla högst tre länkar.' }, 400)
  if (!await sectionDetails(env, sectionId)) return json({ error: 'Avdelningen finns inte.' }, 404)
  if (!await rateLimit(env, `topic:${user.id}`, 60_000)) return json({ error: 'Vänta en minut innan du startar en ny tråd.' }, 429)
  const id = crypto.randomUUID()
  const createdAt = nowIso()
  await env.DB.prepare(`INSERT INTO forum_topics
    (id, section_id, user_id, author_name, title, body, status, created_at, last_activity, views, pinned, locked)
    VALUES (?, ?, ?, ?, ?, ?, 'published', ?, ?, 0, 0, 0)`).bind(id, sectionId, user.id, user.name, title, text, createdAt, createdAt).run()
  return json({ id, message: 'Tråden är publicerad.' }, 201)
}

async function createReply(env: Env, request: Request) {
  const user = await requireUser(env, request)
  const body = await readBody(request)
  const topicId = clean(body.topicId, 80)
  const text = clean(body.body, 1_600)
  if (text.length < 10) return json({ error: 'Svaret måste ha minst tio tecken.' }, 400)
  if (linkCount(text) > 3) return json({ error: 'Ett svar kan innehålla högst tre länkar.' }, 400)
  const topic = await env.DB.prepare("SELECT id, locked FROM forum_topics WHERE id = ? AND status = 'published'").bind(topicId).first<{ id: string; locked: number }>()
  if (!topic) return json({ error: 'Tråden finns inte.' }, 404)
  if (topic.locked) return json({ error: 'Tråden är låst för nya svar.' }, 409)
  if (!await rateLimit(env, `reply:${user.id}`, 15_000)) return json({ error: 'Vänta en liten stund innan du svarar igen.' }, 429)
  const createdAt = nowIso()
  await env.DB.prepare("INSERT INTO forum_replies (id, topic_id, user_id, author_name, body, status, created_at) VALUES (?, ?, ?, ?, ?, 'published', ?)")
    .bind(crypto.randomUUID(), topicId, user.id, user.name, text, createdAt).run()
  await env.DB.prepare('UPDATE forum_topics SET last_activity = ? WHERE id = ?').bind(createdAt, topicId).run()
  return json({ message: 'Svaret är publicerat.' }, 201)
}

async function reportTopic(env: Env, request: Request) {
  const user = await requireUser(env, request)
  const body = await readBody(request)
  const topicId = clean(body.topicId, 80)
  const reason = clean(body.reason, 500)
  if (reason.length < 5) return json({ error: 'Beskriv kort vad som behöver granskas.' }, 400)
  const topic = await env.DB.prepare('SELECT id FROM forum_topics WHERE id = ?').bind(topicId).first()
  if (!topic) return json({ error: 'Tråden finns inte.' }, 404)
  await env.DB.prepare("INSERT INTO forum_reports (id, topic_id, user_id, reason, created_at, status) VALUES (?, ?, ?, ?, ?, 'open')")
    .bind(crypto.randomUUID(), topicId, user.id, reason, nowIso()).run()
  return json({ message: 'Tack. Rapporten är sparad för granskning.' }, 201)
}

async function followTopic(env: Env, request: Request) {
  const user = await requireUser(env, request)
  const body = await readBody(request)
  const topicId = clean(body.topicId, 80)
  const topic = await env.DB.prepare('SELECT id FROM forum_topics WHERE id = ?').bind(topicId).first()
  if (!topic) return json({ error: 'Tråden finns inte.' }, 404)
  await env.DB.prepare('INSERT OR IGNORE INTO forum_follows (user_id, topic_id, created_at) VALUES (?, ?, ?)').bind(user.id, topicId, nowIso()).run()
  return json({ followed: true, message: 'Du följer tråden.' })
}

async function savedArticles(env: Env, request: Request) {
  const user = await requireUser(env, request)
  const articles = (await env.DB.prepare(`SELECT article_id, title, summary, source, url, image, saved_at
    FROM saved_articles WHERE user_id = ? ORDER BY saved_at DESC`).bind(user.id).all()).results || []
  return json({ articles })
}

function safeUrl(value: string) {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' || url.protocol === 'http:'
  } catch {
    return false
  }
}

function safeSavedImage(value: string) {
  return /^\/news-images\/(?:ai\/[a-z0-9-]+\.webp|ai\/articles\/[a-f0-9]{20}-[a-f0-9]{20}-v1\.webp|generated\/[a-f0-9]{20}-[a-f0-9]{20}-v1\.svg)$/.test(value) ? value : ''
}

async function saveArticle(env: Env, request: Request) {
  const user = await requireUser(env, request)
  const body = await readBody(request)
  const id = clean(body.id, 160)
  const title = clean(body.title, 220)
  const summary = clean(body.excerpt, 1_000)
  const source = clean(body.source, 120)
  const url = clean(body.url, 1_000)
  const image = safeSavedImage(clean(body.image, 1_000))
  if (!id || !title || !safeUrl(url)) return json({ error: 'Nyheten kunde inte sparas.' }, 400)
  await env.DB.prepare(`INSERT INTO saved_articles (user_id, article_id, title, summary, source, url, image, saved_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(user_id, article_id) DO UPDATE SET
    title = excluded.title, summary = excluded.summary, source = excluded.source, url = excluded.url, image = excluded.image, saved_at = excluded.saved_at`)
    .bind(user.id, id, title, summary, source, url, image, nowIso()).run()
  return json({ saved: true }, 201)
}

async function updateProfile(env: Env, request: Request) {
  const user = await requireUser(env, request)
  const body = await readBody(request)
  const name = clean(body.name, 40)
  const requestedAvatar = clean(body.avatarUrl, 160)
  if (name.length < 2) return json({ error: 'Namnet måste ha minst två tecken.' }, 400)
  if (requestedAvatar && !PROFILE_AVATARS.has(requestedAvatar)) return json({ error: 'Välj en av Ljusglimts profilbilder.' }, 400)
  await env.DB.prepare('UPDATE users SET name = ?, avatar_url = COALESCE(?, avatar_url) WHERE id = ?').bind(name, requestedAvatar || null, user.id).run()
  await env.DB.prepare('UPDATE forum_topics SET author_name = ? WHERE user_id = ?').bind(name, user.id).run()
  await env.DB.prepare('UPDATE forum_replies SET author_name = ? WHERE user_id = ?').bind(name, user.id).run()
  return json({ user: { ...user, name, avatarUrl: requestedAvatar || user.avatarUrl } })
}

async function handleApi(env: Env, request: Request) {
  const url = new URL(request.url)
  const path = url.pathname
  await ensureDatabase(env)
  if (request.method !== 'GET' && request.method !== 'HEAD') assertSameOrigin(request)

  if (request.method === 'GET' && path === '/api/health') return json({ ok: true, database: true })
  if (request.method === 'GET' && path === '/api/config') return json({ googleClientId: env.GOOGLE_CLIENT_ID || '', googleEnabled: Boolean(env.GOOGLE_CLIENT_ID) })
  if (request.method === 'GET' && path === '/api/auth/me') return json({ user: await currentUser(env, request) })
  if (request.method === 'POST' && path === '/api/auth/register') return handleRegister(env, request)
  if (request.method === 'POST' && path === '/api/auth/login') return handleLogin(env, request)
  if (request.method === 'POST' && path === '/api/auth/logout') return handleLogout(env, request)
  if (request.method === 'POST' && path === '/api/auth/google') return handleGoogleLogin(env, request)
  if (request.method === 'POST' && path === '/api/profile') return updateProfile(env, request)

  if (request.method === 'GET' && path === '/api/forum/index') return json(await forumIndex(env))
  if (request.method === 'GET' && path === '/api/forum/topics') return forumTopics(env, request, clean(url.searchParams.get('section'), 80))
  if (request.method === 'GET' && path === '/api/forum/topic') return forumTopic(env, request, clean(url.searchParams.get('id'), 80))
  if (request.method === 'POST' && path === '/api/forum/topics') return createTopic(env, request)
  if (request.method === 'POST' && path === '/api/forum/replies') return createReply(env, request)
  if (request.method === 'POST' && path === '/api/forum/report') return reportTopic(env, request)
  if (request.method === 'POST' && path === '/api/forum/follow') return followTopic(env, request)
  if (request.method === 'DELETE' && path.startsWith('/api/forum/follow/')) {
    const user = await requireUser(env, request)
    await env.DB.prepare('DELETE FROM forum_follows WHERE user_id = ? AND topic_id = ?').bind(user.id, decodeURIComponent(path.slice('/api/forum/follow/'.length))).run()
    return json({ followed: false })
  }

  if (request.method === 'GET' && path === '/api/saved') return savedArticles(env, request)
  if (request.method === 'POST' && path === '/api/saved') return saveArticle(env, request)
  if (request.method === 'DELETE' && path.startsWith('/api/saved/')) {
    const user = await requireUser(env, request)
    await env.DB.prepare('DELETE FROM saved_articles WHERE user_id = ? AND article_id = ?').bind(user.id, decodeURIComponent(path.slice('/api/saved/'.length))).run()
    return json({ saved: false })
  }

  if (request.method === 'POST' && path === '/api/newsletter') return json({ message: 'Tack! Adressen är kontrollerad men sparas inte ännu.' })
  return json({ error: 'API-adressen finns inte.' }, 404)
}

async function knownArticleSlugs(env: Env, request: Request): Promise<Set<string> | null> {
  try {
    const response = await env.ASSETS.fetch(new Request(new URL('/seo/article-slugs.json', request.url)))
    if (!response.ok) return null
    const value = await response.json()
    if (!Array.isArray(value) || value.some((slug) => typeof slug !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug))) return null
    return new Set(value)
  } catch {
    return null
  }
}

async function articleError(env: Env, request: Request, status: 404 | 503): Promise<Response> {
  let html = '<!doctype html><html lang="sv"><head><title>Ljusglimt</title><meta name="description" content="Ljusglimt"></head><body><div id="root"></div></body></html>'
  let headers = new Headers()
  try {
    const shellResponse = await env.ASSETS.fetch(new Request(new URL('/', request.url)))
    headers = new Headers(shellResponse.headers)
    if (shellResponse.ok) html = await shellResponse.text()
  } catch {
    // The minimal shell below keeps error responses HTML-only even if all assets are unavailable.
  }
  const unavailable = status === 503
  html = html.replace(/<title>[\s\S]*?<\/title>/i, `<title>${unavailable ? 'Nyheterna kan inte nås just nu' : 'Nyheten finns inte'} – Ljusglimt</title>`)
  html = html.replace(/<meta\s+name=["']description["'][^>]*>/i, `<meta name="description" content="${unavailable ? 'Ljusglimts nyheter kan inte nås just nu. Försök igen om en stund.' : 'Den här nyheten finns inte på Ljusglimt.'}">`)
  html = html.replace(/<link\s+rel=["']canonical["'][^>]*>\s*/i, '')
  const robots = '<meta name="robots" content="noindex, nofollow">'
  html = /<meta\s+name=["']robots["'][^>]*>/i.test(html)
    ? html.replace(/<meta\s+name=["']robots["'][^>]*>/i, robots)
    : html.replace('</head>', `${robots}\n</head>`)

  headers.set('content-type', 'text/html; charset=UTF-8')
  headers.set('cache-control', 'no-store')
  headers.delete('content-encoding')
  headers.delete('content-length')
  headers.delete('etag')
  if (unavailable) headers.set('retry-after', '60')
  return new Response(request.method === 'HEAD' ? null : html, { status, statusText: unavailable ? 'Service Unavailable' : 'Not Found', headers })
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try {
      const path = new URL(request.url).pathname
      if ((request.method === 'GET' || request.method === 'HEAD') && path === '/api/news') {
        return env.ASSETS.fetch(new Request(new URL('/data/news.json', request.url), request))
      }
      if (path.startsWith('/api/')) return await handleApi(env, request)
      if ((request.method === 'GET' || request.method === 'HEAD') && path.startsWith('/nyhet/')) {
        let slug = ''
        try {
          slug = decodeURIComponent(path.slice('/nyhet/'.length))
        } catch {
          return env.ASSETS.fetch(request)
        }
        if (slug && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
          const knownSlugs = await knownArticleSlugs(env, request)
          if (!knownSlugs) return articleError(env, request, 503)
          if (!knownSlugs.has(slug)) return articleError(env, request, 404)
          return env.ASSETS.fetch(new Request(new URL(`/seo/articles/${encodeURIComponent(slug)}`, request.url), request))
        }
      }
      return env.ASSETS.fetch(request)
    } catch (error) {
      if (error instanceof Response) return error
      console.error('Ljusglimt Worker error', error)
      return json({ error: 'Något gick fel på servern. Försök igen om en stund.' }, 500)
    }
  },
}
