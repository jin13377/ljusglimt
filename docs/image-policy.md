# Bildpolicy för Ljusglimt

Ljusglimt använder en hybridmodell: verifierade källbilder när användningsrätten
är dokumenterad, annars en automatiskt skapad lokal artikelillustration.

## Kostnadsfria artikelillustrationer

- Skapas lokalt av `scripts/generate_free_article_visuals.py` utan API-anrop.
- Innehåller abstrakta färgfält och former, aldrig rubriktext eller källinnehåll.
- Märks som `Illustration`, inte som ett fotografi från händelsen.
- Varje bild binds till artikelns `id` och `source_fingerprint` och återanvänds
  bara så länge källunderlaget är oförändrat.
- Lagras som SVG i `public/news-images/generated/` och kontrolleras med SHA-256.

## Unika AI-illustrationer

- Märks alltid med texten `AI-illustration` i kort, hero och artikel.
- Bildtexten förklarar att motivet inte dokumenterar händelsen.
- Motivet beskriver ämnet och får inte återskapa verkliga personer, exakta
  platser, logotyper, läsbar text eller påhittade händelsedetaljer.
- Varje bild binds till artikelns `id` och `source_fingerprint`. Om källans
  rubrik, utdrag eller publiceringsdatum ändras blir den gamla bilden ogiltig.
- Generatorn använder `gpt-image-2`, 1280×848 WebP och skapar högst tre
  lyckade bilder per körning. Ett API-fel stoppar aldrig nyhetsflödet.
- Artikelbilder lagras i `public/news-images/ai/articles/`. De sju generella
  reservbilderna ligger direkt i `public/news-images/ai/`.

## Källbilder

En extern bild får bara visas när nyhetsmanifesten uttryckligen innehåller:

- `source_image_verified: true`;
- HTTPS-bildadress utan användaruppgifter;
- fotograf eller korrekt kredit;
- HTTPS-länk till licens, bildkälla eller annat rättighetsunderlag.

Två kontrollerade vägar är tillåtna: en uttrycklig fri licens med skaparkredit,
eller en miniatyrbild som den granskade källan själv har lagt i sitt publika
RSS-/Atom-flöde för syndikering. Den senare visas direkt från en strikt
tillåten bildvärd, krediteras med källans namn och länkar tillbaka till
originalpubliceringen. Godtyckliga bilder som hittas på en artikelsida godtas inte.

Djursektionen kräver alltid `source_image_verified: true`. Artiklar som saknar
en fungerande källbild visas därför inte där och får inte ersättas av en
AI-bild eller lokal illustration.

## Reservkedja

Webben väljer i denna ordning:

1. verifierad källbild;
2. unik AI-illustration för artikeln;
3. kostnadsfri lokal artikelillustration;
4. lokal AI-ämnesbild för kategorin;
5. kodritad illustration om en bildfil ändå inte kan laddas.

RSS-källbilder aktiveras per granskad källa med explicita listor över tillåtna
artikel- och bildvärdar. Good Good Good och The Dodo använder sina egna
flödesminiatyrer; övriga källor fortsätter använda den lokala reservkedjan när
fullständigt bildunderlag saknas.

## Video

Videor kan visas i alla kategorier, men bäddas bara in när ett granskat RSS-,
Atom- eller videoflöde lämnar ett verifierbart YouTube- eller Dailymotion-id.
Exempelvis kan NASA:s RSS-notiser innehålla en officiell YouTube-spelare medan
The Dodos publika flöde använder Dailymotion. Andra värdar och tvetydiga video-id:n
avvisas. Videon laddas först när besökaren trycker på spela och har alltid en
separat länk till källvideon.
