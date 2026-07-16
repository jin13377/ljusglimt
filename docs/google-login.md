# Aktivera Logga in med Google

E-post och lösenord fungerar utan extern konfiguration. Google-knappen behöver
ett OAuth-klient-ID av typen **Web application**.

1. Öppna Google Cloud Console och skapa eller välj ett projekt.
2. Konfigurera OAuth consent screen.
3. Skapa Credentials → OAuth client ID → Web application.
4. Lägg till webbplatsens permanenta HTTPS-adress under **Authorized JavaScript origins**.
   För lokal utveckling kan du även lägga till `http://127.0.0.1:4173`.
5. Öppna din Worker i Cloudflare och välj **Inställningar → Variabler och
   hemligheter**. Lägg till textvariabeln `GOOGLE_CLIENT_ID` med klient-ID:t.
6. Distribuera om Workern. Google-knappen visas automatiskt när variabeln finns.

För lokal Worker-utveckling skapar du filen `.dev.vars` med:

```text
GOOGLE_CLIENT_ID=din-klient.apps.googleusercontent.com
```

Filen är ignorerad av Git och ska inte skickas till GitHub.

Tillfälliga `trycloudflare.com`-adresser byts när tunneln startas om. Google
kräver att varje origin är registrerad, så använd en permanent domän före
offentlig lansering.

Cloudflare Workern verifierar signaturen, webbplatsens klient-ID, utgivaren,
giltighetstiden och att e-postadressen är verifierad. Googles stabila `sub`-fält
används som kontoidentitet. Om samma verifierade e-postadress redan har ett
Ljusglimt-konto kopplas Google-inloggningen till det kontot.
