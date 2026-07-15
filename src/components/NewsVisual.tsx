import { Image as ImageIcon, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { getAiCategoryImage } from '../lib/news'
import type { NewsArticle } from '../types'
import { CategoryArt } from './CategoryArt'

type VisualVariant = 'card' | 'hero' | 'article' | 'search'

export function NewsVisual({ article, variant = 'card', priority = false, showCaption = false }: {
  article: NewsArticle
  variant?: VisualVariant
  priority?: boolean
  showCaption?: boolean
}) {
  const [failedUrls, setFailedUrls] = useState<string[]>([])
  const aiFallback = getAiCategoryImage(article.category)
  const image = article.image.kind === 'source' && failedUrls.includes(article.image.url) ? aiFallback : article.image
  if (failedUrls.includes(image.url)) return <CategoryArt category={article.category} className={`news-visual-fallback visual-${variant}`} />

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
    <span className={`visual-disclosure ${image.kind}`}>
      {image.kind === 'ai' ? <Sparkles size={13} /> : <ImageIcon size={13} />}
      {image.kind === 'ai' ? 'AI-illustration' : 'Källbild'}
    </span>
  </div>

  if (!showCaption) return media
  return <figure className={`news-figure visual-${variant}`}>
    {media}
    <figcaption><span>{image.caption}</span>{image.rightsUrl && <a href={image.rightsUrl} target="_blank" rel="noreferrer">Bildrättigheter</a>}</figcaption>
  </figure>
}
