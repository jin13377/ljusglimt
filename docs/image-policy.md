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
- HTTPS-länk till licens eller annat rättighetsunderlag.

Om ett fält saknas används i stället en lokal artikelillustration. En bildadress i
ett RSS-flöde är endast en kandidat och räknas inte i sig som tillstånd.
Sammanfattningsagenten får inte ändra bild- eller rättighetsfält.

## Reservkedja

Webben väljer i denna ordning:

1. verifierad källbild;
2. unik AI-illustration för artikeln;
3. kostnadsfri lokal artikelillustration;
4. lokal AI-ämnesbild för kategorin;
5. kodritad illustration om en bildfil ändå inte kan laddas.

RSS-källbilder kan bara aktiveras per granskad källa med en explicit lista över
tillåtna bildvärdar och licenser. Kandidaten måste samtidigt innehålla skapare,
ursprung och exakt godkänd licens. Aktiva flöden saknar i nuläget den kompletta
informationen och använder därför den lokala illustrationsreserven.
