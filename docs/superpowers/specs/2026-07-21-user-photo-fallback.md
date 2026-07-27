# Användarbilder som fallback för nyheter utan bild

## Mål
När en hämtad nyhet saknar både verifierad källbild och AI-genererad bild ska
Ljusglimt automatiskt använda en av Daniels egna bilder som bäst matchar
nyhetens innehåll. Bilderna ägs av Daniel (48 st i `Desktop/Ljusglimt`), de är
huvudsakligen AI-genererade motiv och får användas fritt.

## Bildval (innehållsanalys)
För varje nyhet utan bild beräknas en embedding av texten (titel + svensk
rubrik + sammanfattning) och en embedding per användarbild. Den bild med högst
cosine-likhet väljs. Vid flera nyheter i samma vy (startsida/kategori) används
en enkel "redan använd"-spärr så samma bild inte dubbleras i samma lista.

## Arkitektur
- Statiska filer: `public/news-images/user/<slug>.webp` (konverteras från png/jpg).
- Metadata: nytt fält `user_image` på varje artikel i `data/news.json`.
- Matchning: försiggår vid generering (skript) och sparas som `user_image_id`;
  `news.ts` läser bara färdig metadata (ingen runtime-embedding i webbläsaren).
- Prioritet i `resolveNewsImages`: `source` → `ai` → `user` → `category`.

## Teknik
- Embeddings: OpenAI CLIP (`openai/clip-vit-base-patch32`) via `transformers`
  i ComfyUI-venven (redan installerad: torch + transformers). Modellvikter
  cachas lokalt (~600 MB). Inget nätverk vid körning efter första nedladdning.
- Konvertering/resize till 1280×848 WebP via Pillow.

## Globala krav
- Inga nya beroenden i CI (endast lokal körning av matchningsskriptet).
- CI-valideringen måste acceptera `user_image`-fältet så pipelinen inte går sönder.
- Bilderna får inte innehålla riktiga personer (Daniel bekräftade: mest AI-motiv).
- Aldrig skriv över befintlig `source_image_verified` eller `ai_image`.
- Ingen bild får användas två gånger i samma vy-lista (dubletter undviks).
