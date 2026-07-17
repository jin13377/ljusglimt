# Ljusglimt

Projektets samlade nuläge, länkar och driftinformation finns i
[`LJUSGLIMT-PROJEKT.md`](LJUSGLIMT-PROJEKT.md).

En körbar svensk konceptsajt för positiva, konstruktiva och källnära nyheter.
Projektet innehåller en responsiv redaktionell startsida, sök/filter,
originalkällor, ett nyhetsbrevsformulär, ett förhandsmodererat forum och en schemalagd
Codex/RSS-pipeline.

Nyhetsbilder använder verifierade källbilder eller miniatyrer som den granskade
källan själv syndikerar i sitt publika flöde.
Annars skapar natt-/lunchjobbet automatiskt en unik, lokalt lagrad abstrakt
artikelillustration utan API-nyckel eller bildkostnad. En optimerad
illustrationsbank är alltid sista reserv. Se `docs/image-policy.md`.

## Starta lokalt

Installera frontendberoendena en gång och dubbelklicka sedan på
`Starta Ljusglimt.cmd`:

```powershell
npm install
npm run dev
```

Utvecklingsservern öppnas på [http://127.0.0.1:5173](http://127.0.0.1:5173)
och Python-API:t kör på port 4173. Dev-skriptet startar båda processerna och
stänger dem tillsammans med `Ctrl+C`.

För ett produktionslikt lokalt läge:

```powershell
npm run build
python server.py
```

Python serverar då Vite-bygget från `dist/` på
[http://127.0.0.1:4173](http://127.0.0.1:4173). Direkta SPA-länkar och de äldre
adresserna `/forum.html`, `/profil.html` och `/om.html` fortsätter fungera,
även med befintliga query-parametrar. Om Vite ännu inte är installerat kan
Python fortfarande visa den äldre beroendefria frontendversionen.

## Gratis statisk publicering

Projektet är förberett för Cloudflare Workers Static Assets med GitHub som
källa. Använd under Worker-inställningen `Settings > Builds`:

- produktionsgren: `main`
- build command: `npm run build`
- deploy command: `npx wrangler deploy`
- root directory: lämnas tom
- Node.js: 22 eller senare
- obligatoriska environment variables: inga

FÃ¶r verifiering i Google Search Console kan den valfria byggvariabeln
`VITE_GOOGLE_SITE_VERIFICATION` anges med verifieringskoden frÃ¥n Google.
Sidan fungerar utan variabeln. `robots.txt`, `sitemap.xml`, kanoniska adresser,
delningsmetadata och strukturerad nyhetsdata skapas automatiskt vid varje bygge.

Bygget kopierar automatiskt `data/news.json` och `data/seed-news.json` till
`dist/data/`. `wrangler.jsonc` publicerar mappen `dist` och ser till att direkta
länkar i React-appen fungerar som en SPA.

Cloudflare Workern använder D1 för permanent lagring av forum, konton,
sessioner, följda trådar och sparade nyheter. Samma funktioner körs lokalt via
Python-API:t och SQLite när du använder `npm run dev`.

De schemalagda GitHub Actions-jobben kan valfritt använda
`OPENAI_API_KEY` och `OPENAI_IMAGE_API_KEY`. De behövs inte för att bygga eller
visa den statiska webbplatsen.

## Det som fungerar

- startsida med källbelagda svenska sammanfattningar och automatiskt hämtade RSS-notiser;
- särskild Djur-sektion där varje nyhet måste ha en riktig bild från källflödet;
- klickbara, responsiva videor när ett granskat källflöde lämnar säker YouTube- eller Dailymotion-metadata;
- svenska rubriker och sammanfattningar i hela det publika nyhetsflödet; engelska källposter hålls dolda tills svensk text finns;
- kategorifilter, sök, egna artikelsidor och tydlig länk till originalkälla;
- responsiv mobilmeny utan horisontell overflow;
- forum med trådar/svar, rapportering och hastighetsgränser;
- konton med e-post och säkert hashade lösenord;
- personlig profil med sparade nyheter;
- verifierad Google-inloggning när ett Google Client ID konfigurerats;
- manuell forumgranskning via `python scripts/moderate_forum.py`;
- automatisk hämtning och bildkontroll 00:00 och 12:00 Europe/Stockholm, även över sommar-/vintertid;
- kostnadsfria, unika lokala artikelillustrationer vid varje schemalagd körning;
- Codex-agent som bara får skriva källbundna svenska sammanfattningar.

## Aktivera det schemalagda jobbet

1. Publicera projektet i ett GitHub-repository.
2. Lägg in `OPENAI_API_KEY` som GitHub Actions-secret för svenska
   Codex-sammanfattningar. RSS-boten fungerar även utan nyckeln.
3. Ingen bildnyckel behövs. Lokala artikelillustrationer skapas automatiskt.
   `OPENAI_IMAGE_API_KEY` är en helt valfri framtida uppgradering och ska lämnas
   tom om du inte vill ha API-kostnader.
4. Aktivera Actions. Workflow-filen är
   `.github/workflows/positive-news-nightly.yml` och kan även köras manuellt.

Källhämtningen committas innan Codex-steget. Sidan uppdateras därför med
källmaterial även om agentnyckeln saknas eller sammanfattningen misslyckas.
Agenten körs utan sparade Git-uppgifter, styrs av en låst prompt och workflow-
jobbet avvisar andra filer och ändringar av importerade källfält. Endast nya
`agent_summary`-värden kan publiceras av det betrodda slutsteget.

Schemakörningar fyller automatiskt på kostnadsfria, unika SVG-illustrationer.
De skapas av projektets egen deterministiska generator och innehåller ingen
rubriktext, verkliga personer, logotyper eller påhittade händelsedetaljer.
Betald bildgenerering är avstängd så länge ingen API-nyckel finns.

## Testa

```powershell
python -m unittest discover -s tests -v
node --check scripts/dev.mjs
npm run typecheck
npm run lint
npm test
npm run build
```

Läs [automationsdetaljer](docs/automation.md), [forum-API](docs/forum-api.md)
och [designresearch](docs/inspiration.md) för nästa produktionssteg. För Google,
följ [Google-inloggningsguiden](docs/google-login.md).
