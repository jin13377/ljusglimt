# Ljusglimt

En körbar svensk konceptsajt för positiva, konstruktiva och källnära nyheter.
Projektet innehåller en responsiv redaktionell startsida, sök/filter,
originalkällor, nyhetsbrev-demo, ett förhandsmodererat forum och en schemalagd
Codex/RSS-pipeline.

Nyhetsbilder använder en lokal, optimerad AI-illustrationsbank med tydlig
märkning. Verifierade källbilder stöds i datamodellen men visas bara med
fullständig kredit och rättighetslänk. Se `docs/image-policy.md`.

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

## Det som fungerar

- startsida med källbelagda demoartiklar och automatiskt hämtade RSS-notiser;
- kategorifilter, sök, egna artikelsidor och tydlig länk till originalkälla;
- responsiv mobilmeny utan horisontell overflow;
- forum med trådar/svar, honeypot, hastighetsgräns och modereringskö;
- konton med e-post och säkert scrypt-hashade lösenord;
- personlig profil med sparade nyheter;
- Google Identity Services-inloggning när ett Google Client ID konfigurerats;
- manuell forumgranskning via `python scripts/moderate_forum.py`;
- automatisk hämtning 00:00 och 12:00 Europe/Stockholm, även över sommar-/vintertid;
- Codex-agent som bara får skriva källbundna svenska sammanfattningar.

## Aktivera det schemalagda jobbet

1. Publicera projektet i ett GitHub-repository.
2. Lägg in `OPENAI_API_KEY` som GitHub Actions-secret för svenska
   Codex-sammanfattningar. RSS-boten fungerar även utan nyckeln.
3. Aktivera Actions. Workflow-filen är
   `.github/workflows/positive-news-nightly.yml` och kan även köras manuellt.

Källhämtningen committas innan Codex-steget. Sidan uppdateras därför med
källmaterial även om agentnyckeln saknas eller sammanfattningen misslyckas.
Agenten körs utan sparade Git-uppgifter, styrs av en låst prompt och workflow-
jobbet avvisar andra filer och ändringar av importerade källfält. Endast nya
`agent_summary`-värden kan publiceras av det betrodda slutsteget.

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
