# Bildpolicy för Ljusglimt

Ljusglimt använder en hybridmodell: verifierade källbilder när användningsrätten
är dokumenterad, annars en tydligt märkt redaktionell AI-illustration.

## AI-illustrationer

- Märks alltid med texten `AI-illustration` i kort, hero och artikel.
- Bildtexten förklarar att motivet inte dokumenterar händelsen.
- Motivet beskriver ämnet och får inte återskapa verkliga personer, exakta
  platser eller påhittade händelsedetaljer.
- De sju lokala WebP-bilderna ligger i `public/news-images/ai/` och kan laddas
  utan extern spårning eller layoutskiften.

## Källbilder

En extern bild får bara visas när nyhetsmanifesten uttryckligen innehåller:

- `source_image_verified: true`;
- HTTPS-bildadress utan användaruppgifter;
- fotograf eller korrekt kredit;
- HTTPS-länk till licens eller annat rättighetsunderlag.

Om ett fält saknas används AI-illustrationen automatiskt. En bild i ett RSS-
flöde är endast en kandidat och räknas inte i sig som användningstillstånd.
Sammanfattningsagenten får inte ändra bild- eller rättighetsfält.

## Nästa säkra steg för källbilder

När en källa har granskats läggs en explicit bildpolicy till för just den
källan. Godkända bilder bör därefter hämtas till egen lagring, kodas om och
kontrolleras för värd, MIME-typ, filstorlek och dimensioner innan publicering.
