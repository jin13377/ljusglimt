# Forum och medlems-API

Forumet är öppet att läsa men kräver inloggning för trådar, svar och
rapportering. Nya bidrag får status `pending`; författaren ser sitt eget bidrag
medan övriga bara ser `published`.

| Metod | Sökväg | Behörighet | Funktion |
|---|---|---|---|
| `GET` | `/api/forum/topics` | publik | Publicerade trådar, egna väntande trådar och svar |
| `POST` | `/api/forum/topics` | medlem | Skicka ny tråd till moderering |
| `POST` | `/api/forum/replies` | medlem | Skicka svar till moderering |
| `POST` | `/api/forum/report` | medlem | Rapportera en publicerad tråd |
| `GET` | `/api/auth/me` | publik | Aktuell session eller `null` |
| `POST` | `/api/auth/register` | publik | Konto med e-post och lösenord |
| `POST` | `/api/auth/login` | publik | Starta cookie-session |
| `POST` | `/api/auth/google` | publik | Verifiera Google ID-token och starta session |
| `GET/POST/DELETE` | `/api/saved` | medlem | Lista, spara eller ta bort profilens nyheter |

Sessionen ligger i en `HttpOnly`, `SameSite=Lax`-cookie. Lösenord hashades med
scrypt och unika salter. Skrivningar kontrollerar origin, datalängd, ren text
och hastighetsgräns. Rå HTML tillåts inte.

## Moderering

Lista kön:

```powershell
python scripts/moderate_forum.py
```

Godkänn eller avslå:

```powershell
python scripts/moderate_forum.py --approve topic-abc123
python scripts/moderate_forum.py --reject reply-def456
```

SQLite-databasen `data/glimt.db` är lokal och ignoreras av Git. Vid publik
drift ska databasfilen ligga på beständig lagring och regelbundet säkerhetskopieras.
