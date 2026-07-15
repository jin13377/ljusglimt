# Aktivera Logga in med Google

E-post och lösenord fungerar utan extern konfiguration. Google-knappen behöver
ett OAuth-klient-ID av typen **Web application**.

1. Öppna Google Cloud Console och skapa eller välj ett projekt.
2. Konfigurera OAuth consent screen.
3. Skapa Credentials → OAuth client ID → Web application.
4. Lägg till webbplatsens permanenta HTTPS-adress under **Authorized JavaScript origins**.
   För lokal utveckling kan du även lägga till `http://127.0.0.1:4173`.
5. Kopiera `config/local.env.example` till `config/local.env` och ersätt värdet
   med ditt klient-ID.
6. Installera beroenden med `python -m pip install -r requirements.txt` och
   starta om webbplatsen.

Tillfälliga `trycloudflare.com`-adresser byts när tunneln startas om. Google
kräver att varje origin är registrerad, så använd en permanent domän före
offentlig lansering.

Backend verifierar Googles ID-token mot rätt audience och använder Googles
stabila `sub`-fält som kontoidentitet. I produktion används paketet
`google-auth`; tokeninfo-fallbacken finns bara för lokal utveckling.

Ett befintligt lösenordskonto länkas inte automatiskt bara för att Google-
kontot har samma e-postadress. Användaren behöver först logga in med lösenord;
ett uttryckligt kontolänkningsflöde är ett separat produktionssteg.
