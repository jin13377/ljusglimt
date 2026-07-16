# Gladnytt – automation och forumgrund

Det här är automationsmodulen för den positiva nyhetssidan.
Grundkörningen kräver bara Python 3.11 och offentliga RSS/Atom-flöden – ingen
AI-nyckel eller annan hemlighet.

## Snabbstart

```powershell
python scripts/fetch_positive_news.py --force
```

Resultatet skrivs atomiskt till `data/news.json`. Skriptet:

- hämtar endast konfigurerade flöden från `config/feeds.json`;
- behåller källans titel, länk, datum och beskrivning utan att hitta på fakta;
- poängsätter positiva signaler och filtrerar bort tydligt allvarliga ämnen;
- deduplicerar på kanonisk länk och normaliserad rubrik;
- återanvänder tidigare manuella/agentgjorda sammanfattningar;
- hämtar källans egna flödesbilder från strikt tillåtna värdar;
- kopplar verifierade YouTube- och Dailymotion-videor till nyheter i alla kategorier när källflödet lämnar video-id eller säker spelarlänk;
- lägger bara ut engelskspråkiga källposter när en granskad svensk rubrik och sammanfattning finns i `config/swedish-copy.json`;
- skriver först en temporär fil och byter sedan fil atomiskt.

## Dagliga körningar kl. 00 och 12 Europe/Stockholm

Arbetsflödet i `.github/workflows/positive-news-nightly.yml` använder GitHubs
tidszonsmedvetna schema för `Europe/Stockholm` och körs klockan 00:00 och 12:00.
Det gör att sommar- och vintertid hanteras automatiskt. `workflow_dispatch` kan
alltid köras manuellt.

Workflow-jobbet publicerar i tre kontrollerade steg: först källdata, därefter
unika artikelbilder och sist eventuella svenska Codex-sammanfattningar. Varje
steg validerar sin egen tillåtna ändringsmängd innan commit.

Det första bildsteget är alltid kostnadsfritt. En verifierad källbild prioriteras.
Om en publik artikel saknar källbild skapas i stället en deterministisk, abstrakt
SVG utan API-nyckel eller betalningsplan. Om samma artikel återkommer
återanvänds exakt samma bild.
Källtext läggs aldrig i SVG-filen. Ett valfritt senare bildsteg kan använda
`OPENAI_IMAGE_API_KEY`, men körs inte när nyckeln saknas. Manuell körning
aktiverar aldrig det betalda steget om inte `generate_images` väljs uttryckligen.

## Agent-/Codex-sammanfattning

Varje artikel får fältet `agent_summary`. Grundkörningen sätter det till en tom
sträng och bevarar en redan befintlig sammanfattning för samma artikel. Ett
separat Codex-/agentsteg kan därför läsa `data/news.json`, sammanfatta endast
de verifierbara fälten och skriva tillbaka `agent_summary`. Webbplatsen bör visa
källänken intill sammanfattningen och aldrig presentera agenttext som ett
direktcitat.

Se `docs/forum-api.md` för en moderation-first forumstruktur.

### Säker sammanfattningskö

Agenten bör följa `.github/codex/prompts/positive-news-summary.md` och skriva utkast till
`data/summaries.pending.json`. Applicera sedan med:

```powershell
python scripts/apply_agent_summaries.py
```

Appliceringsskriptet kan enbart ändra `agent_summary`, inte importerad rubrik,
källa eller länk. En redaktör bör granska texten före publik användning.
