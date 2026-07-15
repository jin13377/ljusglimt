import { ArrowRight } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { post } from '../lib/api'

export function NewsletterForm({ compact = false }: { compact?: boolean }) {
  const [message, setMessage] = useState('')
  const [error, setError] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const statusId = useId()

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const email = new FormData(form).get('email')
    setSubmitting(true)
    setMessage('')
    setError(false)
    try {
      await post('/api/newsletter', { email })
      setMessage('Tack! Formuläret fungerar. Nyhetsbrevet är inte aktiverat ännu.')
      form.reset()
    } catch (reason) {
      setError(true)
      setMessage(reason instanceof Error ? reason.message : 'Kunde inte ansluta just nu.')
    } finally {
      setSubmitting(false)
    }
  }

  return <form className={compact ? 'footer-newsletter' : 'cta-newsletter'} onSubmit={submit} aria-describedby={message ? statusId : undefined}>
    <div>
      <label className="sr-only" htmlFor={`${statusId}-email`}>E-postadress</label>
      <input id={`${statusId}-email`} type="email" name="email" required placeholder="din@epost.se" autoComplete="email" />
      <button type="submit" disabled={submitting} aria-label={compact ? 'Testa nyhetsbrevsformuläret' : undefined}>
        {compact ? '→' : <>{submitting ? 'Skickar…' : 'Anmäl intresse'} <ArrowRight size={17} /></>}
      </button>
    </div>
    {message && (compact
      ? <small id={statusId} className={error ? 'form-error' : ''} role="status">{message}</small>
      : <p id={statusId} className={`newsletter-status ${error ? 'form-error' : ''}`} role="status">{message}</p>)}
  </form>
}
