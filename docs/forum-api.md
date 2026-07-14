# Forum-MVP: moderation först

Forumet bör börja som en liten, förhandsmodererad del – inte som ett öppet
anonymt kommentarsfält. Användare får läsa publicerade trådar utan konto men
måste vara inloggade för att skicka inlägg.

## Roller och status

- `member`: kan skicka trådar och svar till kön.
- `moderator`: kan godkänna, avslå, låsa och dölja.
- `admin`: kan dessutom hantera moderatorer och avstängningar.
- Innehåll går `pending -> published | rejected`; publicerat innehåll kan senare
  bli `hidden`. Bara `published` returneras i publika listor.

## Minimal API-yta

| Metod | Sökväg | Behörighet | Funktion |
|---|---|---|---|
| `GET` | `/api/forum/threads?cursor=` | publik | Lista publicerade trådar |
| `GET` | `/api/forum/threads/:id` | publik | Läs tråd och publicerade svar |
| `POST` | `/api/forum/threads` | medlem | Skicka tråd till modereringskö |
| `POST` | `/api/forum/threads/:id/replies` | medlem | Skicka svar till kö |
| `POST` | `/api/forum/reports` | medlem | Rapportera innehåll |
| `GET` | `/api/moderation/queue` | moderator | Läs väntande innehåll |
| `POST` | `/api/moderation/:id/decision` | moderator | Godkänn/avslå med orsak |

Alla skrivningar ska ha CSRF-skydd (vid cookie-session), request-body-gräns,
rate limit per konto/IP och servervalidering. Rendera innehåll som ren text i
MVP:n; tillåt inte rå HTML. Logga moderatorbeslut men lagra inte mer persondata
än nödvändigt.

### Exempel: skapa tråd

```json
{
  "title": "Vad gjorde dig glad i dag?",
  "body": "Dela gärna något konkret och vänligt.",
  "category": "vardagsgladje"
}
```

Svar: `202 Accepted`

```json
{
  "id": "thr_01...",
  "status": "pending",
  "message": "Tack! Inlägget granskas före publicering."
}
```

## Rekommenderade skyddsräcken

1. E-postverifiering, visningsnamn och 13-årsgräns i MVP:n.
2. Max 3 nya trådar och 10 svar per konto/timme.
3. Enkel ord-/länkflagga hjälper moderatorn men avslår inte automatiskt.
4. Ingen direktmeddelandefunktion eller bilduppladdning i första versionen.
5. Tydliga regler: vänligt, sant, relevant, ingen reklam eller personangrepp.
6. Rapportknapp på varje publicerat inlägg och snabb döljning vid flera rapporter.

`db/schema.sql` visar en portabel datamodell för SQLite/PostgreSQL. En statisk
förhandsvisning kan använda `docs/forum-sample-public.json`; formuläret ska då tydligt säga
att inskick ännu inte är aktiverat.
