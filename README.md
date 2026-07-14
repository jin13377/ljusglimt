# Ljusglimt

En körbar svensk konceptsajt för positiva, konstruktiva och källnära nyheter.
Projektet innehåller en responsiv redaktionell startsida, sök/filter,
originalkällor, nyhetsbrev-demo, ett förhandsmodererat forum och en nattlig
Codex/RSS-pipeline.

## Starta lokalt

Dubbelklicka på `Starta Ljusglimt.cmd`, eller kör:

```powershell
python server.py
```

Öppna sedan [http://127.0.0.1:4173](http://127.0.0.1:4173).

## Det som fungerar

- startsida med källbelagda demoartiklar och automatiskt hämtade RSS-notiser;
- kategorifilter, sök, artikelmodal och tydlig länk till originalkälla;
- responsiv mobilmeny utan horisontell overflow;
- forum med trådar/svar, honeypot, hastighetsgräns och modereringskö;
- konton med e-post och säkert scrypt-hashade lösenord;
- personlig profil med sparade nyheter;
- Google Identity Services-inloggning när ett Google Client ID konfigurerats;
- manuell forumgranskning via `python scripts/moderate_forum.py`;
- nattlig hämtning exakt 02:00 Europe/Stockholm, även över sommar-/vintertid;
- Codex-agent som bara får skriva källbundna svenska sammanfattningar.

## Aktivera nattjobbet

1. Publicera projektet i ett GitHub-repository.
2. Lägg in `OPENAI_API_KEY` som GitHub Actions-secret för svenska
   Codex-sammanfattningar. RSS-boten fungerar även utan nyckeln.
3. Aktivera Actions. Workflow-filen är
   `.github/workflows/positive-news-nightly.yml` och kan även köras manuellt.

Källhämtningen committas innan Codex-steget. Sidan uppdateras därför med
källmaterial även om agentnyckeln saknas eller sammanfattningen misslyckas.
Agenten körs i `workspace-write`, styrs av en låst prompt och workflow-jobbet
avvisar ändringar utanför de tillåtna datafilerna.

## Testa

```powershell
python -m unittest discover -s tests -v
node --check assets/app.js
node --check assets/forum.js
```

Läs [automationsdetaljer](docs/automation.md), [forum-API](docs/forum-api.md)
och [designresearch](docs/inspiration.md) för nästa produktionssteg. För Google,
följ [Google-inloggningsguiden](docs/google-login.md).
