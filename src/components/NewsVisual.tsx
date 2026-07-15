import { Image as ImageIcon } from 'lucide-react'
import { useState } from 'react'
import { getAiCategoryImage } from '../lib/news'
import type { NewsArticle, NewsImage } from '../types'
import { AiImageBadge } from './AiImageBadge'
import { CategoryArt } from './CategoryArt'

type VisualVariant = 'card' | 'hero' | 'article' | 'search'

export function NewsVisual({ article, variant = 'card', priority = false, showCaption = false }: {
  article: NewsArticle
  variant?: VisualVariant
  priority?: boolean
  showCaption?: boolean
}) {
  const [failedUrls, setFailedUrls] = useState<string[]>([])
  const candidates = [article.image, article.fallbackImage, getAiCategoryImage(article.category)]
    .filter((candidate): candidate is NewsImage => Boolean(candidate))
    .filter((candidate, index, images) => images.findIndex((image) => image.url === candidate.url) === index)
  const image = candidates.find((candidate) => !failedUrls.includes(candidate.url))
  if (!image) return <CategoryArt category={article.category} className={`news-visual-fallback visual-${variant}`} />

  const media = <div className={`news-visual visual-${variant}`}>
    <img
      src={image.url}
      width={image.width}
      height={image.height}
      alt={showCaption ? image.alt : ''}
      loading={priority ? 'eager' : 'lazy'}
      fetchPriority={priority ? 'high' : 'auto'}
      decoding="async"
      referrerPolicy={image.kind === 'source' ? 'no-referrer' : undefined}
      onError={() => setFailedUrls((urls) => urls.includes(image.url) ? urls : [...urls, image.url])}
    />
    {image.kind === 'ai'
      ? <AiImageBadge />
      : <span className="visual-disclosure source"><ImageIcon size={13} />Källbild</span>}
  </div>

  if (!showCaption) return media
  return <figure className={`news-figure visual-${variant}`}>
    {media}
    <figcaption><span>{image.caption}</span>{image.rightsUrl && <a href={image.rightsUrl} target="_blank" rel="noreferrer">Bildrättigheter</a>}</figcaption>
  </figure>
}
