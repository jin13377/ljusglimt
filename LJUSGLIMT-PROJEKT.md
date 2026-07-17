# Ljusglimt – projektcentral

Senast uppdaterad: 17 juli 2026

Det här är projektets gemensamma översikt. Börja här vid framtida arbete i Codex och kontrollera sedan alltid den aktuella koden, Git-statusen och den publika sidan innan något ändras.

## Snabblänkar

- Publik webbplats: <https://ljusglimt.daniel-eklund1981.workers.dev/>
- GitHub: <https://github.com/jin13377/ljusglimt>
- GitHub Actions: <https://github.com/jin13377/ljusglimt/actions>
- Lokal utveckling: <http://127.0.0.1:5173/>
- Lokalt produktionsläge: <http://127.0.0.1:4173/>

## Syfte

Ljusglimt är en svensk nyhetssida som samlar positiva, konstruktiva och källnära nyheter. Besökaren ska snabbt förstå vad som har hänt, se var uppgifterna kommer från och kunna öppna originalkällan.

Grundprinciper:

- svenska används i hela det publika gränssnittet;
- källan är alltid facit och ska vara tydligt länkad;
- allvarliga, vilseledande eller osäkra kandidater filtreras bort;
- verkliga källbilder prioriteras;
- djurnyheter visas endast med en riktig bild från källflödet;
- video spelas på nyhetssidan när källan lämnar verifierad YouTube- eller Dailymotion-information;
- automatiken får inte hitta på fakta, citat, bilder av verkliga händelser eller källor;
- sidan ska fungera på mobil, surfplatta och dator.

## Nuläge

Fungerande delar:

- responsiv startsida, artikelsidor, sökning, filter och kategorier;
- en särskild avdelning för glada djurnyheter;
- “Dagens ljusglimt” roterar mellan aktuella svenska källnyheter per kalenderdag i Stockholm och använder en fast källsammanfattning endast som reserv;
- nyheter hämtas automatiskt klockan 00:00 och 12:00 svensk tid;
- verifierade källbilder, lokala reservillustrationer och verifierade källvideor;
- forum med huvudgrupper, trådar, svar, rapportering, moderering och hastighetsgränser;
- konton med e-post/lösenord och Google-inloggning;
- valbara positiva profilikoner;
- sparade nyheter på användarens profil;
- Search Console-verifiering, `robots.txt`, webbplatskarta och delningsmetadata;
- permanent publicering via Cloudflare Workers och D1.

## Teknik

Frontend:

- React och TypeScript
- Vite
- Tailwind CSS
- Framer Motion
- Lucide React

Backend och lagring:

- Cloudflare Worker i `worker/index.ts`
- Cloudflare D1-databasen `ljusglimt-forum`
- Python-API och SQLite för lokal utveckling

Automation:

- GitHub Actions i `.github/workflows/positive-news-nightly.yml`
- Python-pipeline i `scripts/fetch_positive_news.py`
- tillåtna källor och filter i `config/feeds.json`
- publicerade nyhetsdata i `data/news.json`

## Så fungerar den automatiska uppdateringen

1. GitHub Actions startar klockan 00:00 och 12:00 i tidszonen `Europe/Stockholm`.
2. Endast källor i `config/feeds.json` hämtas.
3. Kandidater poängsätts, ålderskontrolleras, filtreras och dedupliceras.
4. Godkända källbilder och videor kopplas till rätt artikel.
5. En kostnadsfri lokal SVG-illustration skapas om en vanlig nyhet saknar godkänd källbild.
6. Nyhetsdata och bilder sparas i GitHub.
7. Cloudflare visar den uppdaterade sidan.

Automatiken körs i molnet. Daniels dator, Codex och Hermes behöver inte vara igång. GitHub kan starta jobbet några minuter sent, men schemaperioden hanteras ändå korrekt och dubbla körningar stoppas.

## Bilder och video

Prioriteringsordning:

1. verifierad bild från nyhetskällans eget flöde;
2. unik artikelbild från den valfria bildtjänsten, endast om en betald nyckel någon gång aktiveras;
3. kostnadsfri lokal SVG-illustration;
4. lokal kategoriillustration som sista reserv.

Den föredragna illustrationsriktningen när den passar nyheten är varm papperscollage med organiska lager, dämpat grönt, sand, gult, ljusblått och korall. Bilder ska inte innehålla inbakad rubriktext och ska undvika ett blankt, generiskt AI-uttryck. Stilen är en möjlighet, inte ett krav för varje nyhet.

Djurnyheter får inte ersätta en saknad källbild med en påhittad djurbild. Nyheten ska då inte visas i djuravdelningen.

## Konton och forum

- Cloudflare D1 lagrar konton, sessioner, forumtrådar, svar, följda trådar och sparade nyheter permanent.
- E-post/lösenord fungerar utan extern tjänst.
- Google-inloggning använder Worker-variabeln `GOOGLE_CLIENT_ID` och är aktiverad på den publika sidan.
- Nya foruminlägg hanteras med moderering och rapporteringsfunktioner.
- Lokal manuell granskning kan göras med `python scripts/moderate_forum.py`.

Publicera aldrig lösenord, OAuth-uppgifter, sessionsnycklar eller API-nycklar i Git.

## Publicering och kostnader

Nuvarande webbpublicering använder Cloudflares kostnadsfria nivå och GitHub Actions. En egen `.se`-domän ingår inte och skulle behöva köpas separat.

Obligatoriska hemliga nycklar för att bygga och visa webbplatsen: inga.

Konfiguration som används eller kan användas:

- `GOOGLE_CLIENT_ID` – Google-inloggning i Cloudflare Worker; redan aktiverad publikt.
- `VITE_GOOGLE_SITE_VERIFICATION` – valfri Search Console-kod vid bygge.
- `OPENAI_API_KEY` – valfri betald svensk Codex-sammanfattning i GitHub Actions; behövs inte för RSS-hämtning.
- `OPENAI_IMAGE_API_KEY` – valfri betald bildgenerering; ska lämnas tom för kostnadsfri drift.

ChatGPT-inloggning och OpenAI API är skilda saker. En ChatGPT-prenumeration ger inte automatiskt kostnadsfria API-anrop.

## Viktiga kommandon

Från projektmappen i Kommandotolken:

```cmd
npm install
npm run dev
```

Det går också att dubbelklicka på `Starta Ljusglimt.cmd`.

Full kontroll:

```cmd
python -m unittest discover -s tests -v
npm run typecheck
npm run lint
npm test
npm run build
```

Publicering:

```cmd
npm run deploy:cloudflare
```

Git:

```cmd
git status
git add .
git commit -m "beskriv ändringen"
git push origin main
```

Schemakörningen kan granskas på GitHub Actions-länken ovan. En lyckad körning ska ha jobbet `update-news` med grön status.

## Viktiga filer

- `src/pages/HomePage.tsx` – startsidan och Dagens ljusglimt
- `src/lib/news.ts` – normalisering, bildval, språkfilter och dagligt huvudnyhetsval
- `worker/index.ts` – publikt API, forum, konton och Google-inloggning
- `scripts/fetch_positive_news.py` – källhämtning och redaktionella filter
- `config/feeds.json` – tillåtna nyhetskällor
- `config/swedish-copy.json` – granskad svensk text för utländska källor
- `data/news.json` – aktuellt automatiskt nyhetsflöde
- `data/seed-news.json` – fasta källsammanfattningar och säker reserv
- `wrangler.jsonc` – Cloudflare Worker, statiska filer och D1-bindning
- `.github/workflows/positive-news-nightly.yml` – molnschemat

## Fördjupad dokumentation

- `docs/automation.md` – nyhetspipeline och schema
- `docs/image-policy.md` – bildregler och källrättigheter
- `docs/forum-api.md` – forumets API och moderering
- `docs/google-login.md` – Google-inloggning
- `docs/inspiration.md` – redaktionell och visuell riktning

## Rekommenderad arbetsordning framåt

1. Låt 00- och 12-körningarna samla verkliga resultat under några dagar.
2. Granska kvalitet, aktualitet, dubbletter, svenska texter, bilder och videor.
3. Följ indexering och söktrafik i Google Search Console.
4. Utveckla administrativ moderering först när forumet börjar få riktiga användare.
5. Lägg inte till funktioner utan ett tydligt användarbehov.

## Klart betyder

En ändring är inte klar förrän typkontroll, lint, tester och produktionsbygge är godkända. Synliga ändringar ska dessutom kontrolleras på både dator och mobil. Vid publicering ska den riktiga Cloudflare-adressen verifieras efter distributionen.
