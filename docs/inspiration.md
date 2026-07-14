# Inspirationsunderlag för en positiv nyhetssajt

Det här är ett eget designunderlag, inspirerat av etablerade redaktionella mönster. Inga logotyper, komponenter, texter eller unika layouter ska kopieras.

## Vad etablerade nyhetssidor gör bra

- **En tydlig förstasida, inte ett jämnt kortflöde.** Dagens viktigaste berättelse får störst rubrik och bild. Därefter följer ett fåtal sekundära nyheter och sedan ämnessektioner. Storlek och placering ska visa prioritet innan besökaren har läst ett ord.
- **En stabil masthead och kort ämnesnavigation.** Nyheter, Sverige, Världen, Miljö, Vetenskap, Människor och Forum räcker i första nivån. Sök och konto är verktyg, inte ämnen.
- **Kort är riktiga dokumentdelar.** BBC GEL rekommenderar semantiska listor och korrekt rubrikhierarki för samlingar av kort. Bild, rubrik, sammanfattning, källa och tid ska därför ha konsekvent ordning och fungera med tangentbord och skärmläsare. Se [BBC GEL: Cards](https://bbc.github.io/gel/components/cards/) och [BBC GEL: teknisk dokumentation](https://bbc.github.io/gel/).
- **Sektioner får egen identitet utan att sajten splittras.** The Guardians designsystem använder färg för redaktionella sektioner och betonar tydlig avsikt och klarhet. För den här sajten bör färgen vara en liten kategoriaccent, inte ett helt nytt tema per sida. Se [The Guardian Design System](https://guardian.github.io/theguardian.design/).
- **Förtroende syns i gränssnittet.** Reuters betonar korrekthet före snabbhet, namngivna källor, tydlig attribuering och öppna rättelser. Det ska översättas till synlig källa, publiceringstid, uppdateringstid och rättelsehistorik. Se [Reuters Journalistic Standards](https://reutersagency.com/about/standards-values/) och [Thomson Reuters Trust Principles](https://www.thomsonreuters.com/en/about-us/trust-principles).
- **Avsändaren är lätt att förstå.** Google News lyfter byline, datum, innehållstyp, författarprofil, redaktionella regler, ägare och kontaktvägar som konkreta transparenssignaler. Se [Google om transparens för nyhetskällor](https://developers.google.com/search/blog/2021/06/google-news-sources).

## Rekommenderad informationshierarki

### Förstasida på desktop

1. Kompakt toppfält: logotyp, datum, sök, konto och knapp till forumet.
2. Ämnesnavigation med högst sju val och en tydlig aktiv kategori.
3. Hero: en huvudnyhet med stor bild, kategori, rubrik, två rader ingress, källa och tid.
4. Två till fyra sekundära nyheter i en tätare grid.
5. Raden **Snabba glädjeämnen** för korta verifierade notiser.
6. Ämnessektioner med en ledande artikel plus tre mindre artiklar.
7. **Nära dig** för lokala positiva nyheter.
8. **Samtalet just nu** med tre modererade forumtrådar.
9. Nyhetsbrev och sidfot med redaktion, metod, rättelser, källpolicy och kontakt.

### Mobil

- En kolumn och samma redaktionella ordning som desktop.
- Hero först, sedan sekundära artiklar; undvik att flytta upp forum eller annonser över dagens viktigaste nyhet.
- Horisontell ämnesnavigation får scrolla men ska ha synlig fokusmarkering.
- Bildformat 16:9 i listor; rubriker får högst tre synliga rader.
- Minst 44 × 44 px tryckyta, synlig tangentbordsfokus och stöd för reducerad rörelse.

## Visuellt uttryck

- **Ton:** varm, lugn och redaktionell — inte barnslig och inte wellness-reklam.
- **Bas:** varmvit bakgrund, mörk marin text, diskreta grå linjer och en klar grön huvudaccent.
- **Kategoriaccenter:** exempelvis blå för vetenskap, turkos för miljö, korall för människor och gul för kultur. Kontrollera alltid WCAG-kontrast.
- **Typografi:** uttrycksfull men lättläst rubrikstil kombinerad med neutral sans-serif för brödtext och metadata. Brödtext omkring 18 px på artikelsidor.
- **Bilder:** dokumentära motiv med människor, platser och faktiska händelser. Undvik generiska leenden, övermättnad och AI-bilder som kan misstolkas som journalistiskt material.
- **Rörelse:** endast mjuka tillståndsbyten på 150–220 ms. Ingen autoplay eller ständigt rullande ticker.

## Positiv journalistik utan trovärdighetsproblem

- Publicera **lösnings- och framstegsnyheter**, inte bara feelgood. Beskriv både resultatet och vad som återstår.
- Varje artikel ska ha originalkälla, länk, källdatum, ansvarig redaktör och status: `Verifierad`, `Uppdaterad` eller `Rättad`.
- En Codex-agent får föreslå och sammanfatta artiklar, men en post ska ligga som utkast tills automatiska kontroller har hittat en nåbar originalkälla och en redaktionell kontroll är godkänd.
- Märk AI-assistans öppet på metodsidan. Låt aldrig en bot hitta på citat, personer, siffror, bildtexter eller lokala händelser.
- Separera `Nyhet`, `Analys`, `Debatt`, `Partnerinnehåll` och `Demo` visuellt och semantiskt.
- Visa en kort **Varför är detta positivt?**-rad, men håll den faktabaserad: exempelvis “Fler barn nås av vaccin” i stället för värdeord som “fantastiskt”.

## Forum som känns tryggt och seriöst

- Forumet ska heta något i stil med **Samtalet** och ligga efter nyhetsinnehållet på startsidan.
- Kräv verifierad e-post för att skriva; läsning kan vara öppen.
- Visa regler före första inlägget: vänlig ton, saklig kritik, inga personangrepp, ingen desinformation och inga personuppgifter.
- Inbyggd rapportering, länk till modereringsbeslut och tydlig markering av redaktion, moderator och vanlig medlem.
- Begränsa nya konton, länkar och upprepade inlägg. Håll misstänkt innehåll för granskning i stället för att publicera direkt.
- Koppla diskussioner till artiklar men visa dem aldrig som en del av den redaktionella texten.

## Komponenter att bygga först

1. Masthead och responsiv ämnesnavigation.
2. Hero och tre kortstorlekar: stor, standard och kompakt.
3. Gemensam metadatarad: kategori, källa, publicerad/uppdaterad och lästid.
4. Källruta på artikelsidan med originallänk och verifieringsdatum.
5. Ämnessektion med konsekvent rubrikhierarki.
6. Forumkort och modereringsstatus.
7. Tom-, laddnings- och felläge för det nattliga nyhetsflödet.

## Undvik

- Ett rutnät där alla nyheter ser lika viktiga ut.
- Glada emojis, konfetti och pastell på varje komponent.
- Rubriker som lovar mer än källan visar.
- Otydliga `Läs mer`-länkar; länka hela rubriken med ett unikt namn.
- Karuseller för huvudnyheter, autoplay-video och oändlig scroll.
- Publicering direkt från en agent utan käll- och kvalitetskontroll.
- Kommentarssiffror som konkurrerar med källa och publiceringstid.

## Praktisk designriktning

En bra målbild är **morgontidningens lugn + modern kortstruktur + synlig källkedja**. Positiviteten ska märkas i urvalet och den mänskliga värmen, medan strukturen ska kännas lika stringent som på en traditionell nyhetssajt.
