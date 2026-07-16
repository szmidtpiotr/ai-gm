---
typ: pomysl
status: szkic
zrodlo: "#1193"
---

# Wydarzenia regionalne — żywy świat

## Co gracz dostaje
Raz na jakiś czas region dostaje wydarzenie, które realnie zmienia grę — a gracz dowiaduje się o nim z narracji, plotek i cen w sklepie. Świat zmienia się, nawet gdy on nic nie robi.

## Jak to działa
Przykładowe wydarzenia:
- **Jarmark** — ceny w sklepach −20%, nowe towary u kupców, tłum w osadzie (narracja);
- **Zaraza** — droższe mikstury, NPC w kapturach, nowe kontrakty na tablicy („znajdź zielarza"), ryzyko choroby przy odpoczynku w mieście;
- **Rajdy bandytów** — częstsze encountery na traktach regionu, ale lepszy loot z bandytów;
- **Surowa zima / susza** (sezonowe) — wyższe koszty podróży, opisowa pogoda spójna z systemem z FAZY PT.

Event to rekord z modyfikatorami: region, typ, czas trwania, mnożnik cen per kategoria, mnożnik wag encounterów, tagi narracyjne wstrzykiwane do promptu narratora, flagi specjalne. Technicznie: `game_config_event_templates` (szablony) + `world_events` (aktywne instancje); serwis `world_event_service.get_active_events(region)` jako single source; losowanie przy day-ticku podróży (mała szansa dzienna, **max 1 aktywny event per region**). Integracje wpinane małymi krokami: sklep (mnożnik cen), encountery (mnożnik wag), narrator (tagi jak pogoda z FAZY PT), plotki/kontrakty (event jako źródło hooków). Po stronie gracza celowo **brak dedykowanego UI** — świat komunikuje event przez narrację i ceny (ewentualnie ikonka przy regionie na mapie).

## Zarządzanie (admin)
Panel Świat → zakładka „Wydarzenia": lista aktywnych eventów per region; przyciski „wylosuj" / „zakończ" / „dodaj ręcznie". Start ręczny lub z prostego schedulera.

## Dlaczego pasuje do gry
FAZA RM daje regiony jako tagi, travel daje encountery i day-tick, sklep ma ceny, narrator ma compose_narrator_system_prompt — wydarzenie to **tylko warstwa modyfikatorów na istniejących systemach**. Duży efekt „żywego świata" przy małej mechanice.

## Liczby startowe
- Mnożniki (np. **−20%** na jarmarku), szansa dzienna na event, czasy trwania — startowe, tuning po obserwacji.

## Zależności i powiązania
- **FAZA RM (regiony) — blokująca dla pełnej wersji**; do tego czasu można działać na jednym regionie „kresy" (resolve_region defensywnie zwraca kresy).
- FAZA PT day-tick — jest.
- Eventy zasilają [[System plotek w karczmach]] i podsuwają kontrakty na [[Tablica zleceń — bounty board]]; są też głównym źródłem wieści dla [[Kurier Kresowy — gazeta świata]].

## Out of scope
- Łańcuchy eventów (zaraza → kwarantanna → bunt) — v2.
- Eventy globalne całego świata.

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1193
