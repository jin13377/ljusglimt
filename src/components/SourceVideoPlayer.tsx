import { ExternalLink, Play } from 'lucide-react'
import { useState } from 'react'
import type { NewsImage, NewsVideo } from '../types'

export function SourceVideoPlayer({ video, poster }: { video: NewsVideo; poster: NewsImage }) {
  const [playing, setPlaying] = useState(false)
  const separator = video.embedUrl.includes('?') ? '&' : '?'
  const embedUrl = `${video.embedUrl}${separator}${video.provider === 'youtube' ? 'autoplay=1&rel=0' : 'autoplay=1'}`
  const platform = video.provider === 'youtube' ? 'YouTube' : 'Dailymotion'

  return <section className="source-video" aria-labelledby="source-video-title">
    <header>
      <div>
        <span className="eyebrow">Video från källan</span>
        <h2 id="source-video-title">Se djurglimten här</h2>
      </div>
      <a href={video.sourceUrl} target="_blank" rel="noreferrer">Öppna på {platform} <ExternalLink size={15} /></a>
    </header>
    <div className="source-video-frame">
      {playing
        ? <iframe
            src={embedUrl}
            title={video.title}
            loading="lazy"
            referrerPolicy="strict-origin-when-cross-origin"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          />
        : <button type="button" className="source-video-poster" onClick={() => setPlaying(true)} aria-label={`Spela videon: ${video.title}`}>
            <img src={poster.url} alt="" loading="lazy" referrerPolicy={poster.kind === 'source' ? 'no-referrer' : undefined} />
            <span><Play fill="currentColor" /> Spela video</span>
          </button>}
    </div>
    <p>Videon bäddas in från {platform} först när du trycker på spela.</p>
  </section>
}
