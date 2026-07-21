# Juggernaut XL vs Z-Image-Turbo – bildjämförelse

## Mål
Skapa två fristående provbilder för samma representativa Ljusglimt-nyhet: en med Juggernaut XL v9 och en med Z-Image-Turbo. Ingen produktionsdata eller livebild får ändras.

## Gemensamma krav
- Samma konkreta engelska motiv och redaktionella fotoinriktning.
- Samma bildförhållande och slutstorlek: 1280 × 848 WebP.
- Ingen text, logotyp, vattenstämpel eller rubrik i bilden.
- Naturligt ljus, realistiskt och relevant för den valda nyheten.

## Genomförande
1. Välj en publicerad nyhet med tydligt visuellt motiv.
2. Starta lokal ComfyUI på loopback.
3. Generera exakt en Juggernaut-bild och exakt en Z-Image-bild.
4. Kontrollera dimensioner, pixelvariation, textartefakter, relevans och skärpa.
5. Skapa en lokal HTML-jämförelse och öppna den i användarens webbläsare.

## Säkerhet
- Ingen massgenerering.
- Ingen ändring av `data/news.json`.
- Ingen commit/push/deploy av provbilder.
- Originalbilderna på Ljusglimt lämnas orörda tills användaren väljer modell.
