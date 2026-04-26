# HANDOFF

Ten pakiet jest przygotowany pod adaptacje UI 1:1 do Figmy przy minimalnych zmianach logiki.

## Cel

- Zachowac obecny backend i flow aplikacji.
- Wymienic glownie warstwe wizualna (HTML/CSS i czesci template stringow w JS).
- Nie zrywac kontraktow DOM/API wykorzystywanych przez `frontend/js/*.js`.

## Co dostaje Figma

- `SPEC_UI_ADAPTATION.md` - glowna specyfikacja wdrozenia.
- `SCREEN_INVENTORY.md` - lista ekranow i stanow UI.
- `DOM_CONTRACT.md` - selektory, ktorych nie wolno zmieniac.
- `API_INTEGRATION_ASSUMPTIONS.md` - kontrakty API dla frontendu.
- `TOKEN_MAP.md` - mapowanie tokenow Figma -> CSS.
- `IMPLEMENTATION_DIFF_GUIDE.md` - jak bezpiecznie wdrazac diff.

## Zasada wdrozenia

1. Najpierw zachowaj kontrakty z `DOM_CONTRACT.md`.
2. Potem odwzoruj layout i tokeny.
3. Na koncu podmieniaj markup wewnatrz istniejacych kontenerow.

## Zakres "do not break"

- Nie zmieniac ID podpinanych w `window.getEls()`.
- Nie zmieniac endpointow i payloadow bez rownoleglego update JS.
- Nie usuwac obslugi SSE dla `/api/campaigns/{campaign_id}/turns/stream`.
