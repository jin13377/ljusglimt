export function AiImageBadge() {
  return (
    <span className="visual-disclosure ai" title="AI-genererad illustration">
      <svg className="ai-compass" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
        <circle className="ai-compass-orbit" cx="16" cy="16" r="12.25" />
        <path className="ai-compass-ticks" d="M16 1.75v3M30.25 16h-3M16 30.25v-3M1.75 16h3" />
        <path className="ai-compass-north" d="M16 4.7 18.35 11.7 16 10.45l-2.35 1.25Z" />
        <path className="ai-compass-needle" d="M16 8.25 18 14l5.75 2-5.75 2-2 5.75L14 18l-5.75-2L14 14Z" />
        <circle className="ai-compass-core" cx="16" cy="16" r="6.25" />
      </svg>
      <span className="ai-monogram" aria-hidden="true">AI</span>
      <span className="sr-only">AI-genererad illustration</span>
    </span>
  )
}
