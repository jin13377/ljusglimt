import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return <section className="page-wrap state-page"><Compass /><span className="eyebrow">404</span><h1>Den här ljusglimten finns inte</h1><p>Länken kan vara gammal eller felskriven.</p><Link className="button primary" to="/">Till startsidan</Link></section>
}
