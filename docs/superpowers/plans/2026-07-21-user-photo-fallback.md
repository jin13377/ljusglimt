# Användarbilder som fallback – implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Låt Ljusglimt använda Daniels egna bilder som innehållsmatchad fallback när en nyhet saknar källa/AI-bild.

**Architecture:** Importera 48 bilder till `public/news-images/user/`, beräkna CLIP-embeddings (text+ bild) lokalt, spara bästa `user_image_id` per nyhet i `news.json`, och lägg till en `user`-nivå i `resolveNewsImages` samt tillåt fältet i CI-valideringen.

**Tech Stack:** Python, ComfyUI-venvens transformers (CLIP), Pillow, TypeScript (news.ts, types.ts).

## Global Constraints
- Inga nya CI-beroenden; matchningsskript körs bara lokalt.
- CI-validering måste acceptera `user_image`.
- Prioritet: source → ai → user → category.
- Inga dubbletter av samma bild i en vy.

---

### Task 1: Importera och konvertera bilder
**Files:** Create `public/news-images/user/*.webp`
**Interfaces:** Produces 48 webp-filer (1280×848) med sluggar från originalfilnamn.
- [ ] Kopiera 48 bilder från `Desktop/Ljusglimt` till `public/news-images/user/`.
- [ ] Konvertera png/jpg till WebP 1280×848 med Pillow.
- [ ] Verifiera antal och dimensioner.

### Task 2: Embedding- och matchningsskript
**Files:** Create `scripts/match_user_images.py`
**Interfaces:** Consumes `public/news-images/user/*.webp` + `data/news.json`. Produces `user_image_id` per berörd artikel.
- [ ] Ladda CLIP via transformers (openai/clip-vit-base-patch32).
- [ ] Beräkna bild-embeddings för alla user-bilder, text-embeddings för nyheter utan bild.
- [ ] Spara `user_image` block (url, alt, user_image_id, width, height) på artiklarna.
- [ ] Respektera source/ai redan satta; rör inte dem.

### Task 3: TypeScript-stöd för user_image
**Files:** Modify `src/types.ts`, `src/lib/news.ts`
**Interfaces:** Lägger till `user`-nivå i bildupplösningen.
- [ ] Lägg till `RawUserNewsImage` och `user_image?` i `RawFetchedNews`/`NewsArticle`.
- [ ] Utöka `NewsImageKind` med `'user'`.
- [ ] Implementera `resolveUserImage` och infoga i `resolveNewsImages` efter ai.

### Task 4: Tillåt fältet i CI-validering
**Files:** Modify `scripts/validate_generated_image_changes.py`, `scripts/validate_agent_news_changes.py`
**Interfaces:** Förhindrar att pipelinen går sönder av nya fältet.
- [ ] Ignorera `user_image` i "non-image fields changed"-kontrollen.
- [ ] Dokumentera att user_image inte räknas som genererad bild.

### Task 5: Bygg, verifiera, publicera
**Files:** `npm run build`, deploy
- [ ] Typecheck + build grönt.
- [ ] Verifiera live att en bildlös nyhet visar user-bild.
- [ ] Commit i små omgångar, push, deploy.
