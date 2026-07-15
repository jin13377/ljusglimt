import { FlaskConical, HeartPulse, Leaf, Lightbulb, Palette, Sparkles, Users } from 'lucide-react'

const styles: Record<string, { from: string; to: string; icon: typeof Leaf }> = {
  Miljö: { from: '#dcecdf', to: '#8dbb9b', icon: Leaf },
  Natur: { from: '#e2efcf', to: '#9ebf71', icon: Leaf },
  Hälsa: { from: '#f8ddd5', to: '#e79880', icon: HeartPulse },
  Vetenskap: { from: '#dce8f5', to: '#91afd3', icon: FlaskConical },
  Kultur: { from: '#efe0f0', to: '#b98cbd', icon: Palette },
  Människor: { from: '#f8e8bd', to: '#dfb552', icon: Users },
  Framsteg: { from: '#e5e2f2', to: '#aaa0ce', icon: Lightbulb },
}

export function CategoryArt({ category, className = '' }: { category: string; className?: string }) {
  const palette = styles[category] || styles.Framsteg
  const Icon = palette.icon
  return (
    <div className={`category-art ${className}`} style={{ '--art-from': palette.from, '--art-to': palette.to } as React.CSSProperties}>
      <span className="art-orbit art-orbit-one" />
      <span className="art-orbit art-orbit-two" />
      <Icon aria-hidden="true" strokeWidth={1.35} />
      <span className="art-label"><Sparkles size={13} /> Ämnesillustration</span>
    </div>
  )
}
