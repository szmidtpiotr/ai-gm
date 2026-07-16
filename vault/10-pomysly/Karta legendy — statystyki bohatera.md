---
typ: pomysl
status: szkic
zrodlo: "#1213"
---

# Karta legendy — statystyki życiowe bohatera

## Co gracz dostaje
Ekran „Karta legendy" w karcie postaci — liczniki z całego życia bohatera (cross-kampanijne, model Hero-First). Czysta ciekawostka w stylu „Spotify Wrapped" — zero wpływu na balans. Ludzie to kochają i wracają, żeby podbić liczniki.

## Jak to działa
Liczniki:
- tury zagrane, rzuty kośćmi ogółem;
- liczba Nat 20 i Nat 1 (+ „szczęście życiowe": stosunek);
- najczęściej zabijany wróg, łączna liczba zabójstw;
- złoto zarobione vs wydane (w tym: przepite/przegrane w kości);
- przebyte heksy, odkryte lokacje;
- wygrane/przegrane w kości (gambling);
- ukończone kampanie / lochy.

Technicznie: `legend_stats_service` z agregacjami per character (cross-kampanijnie po character_id), liczone on-read (tabele są małe); UI to siatka kafelków z liczbami, styl spójny z Kroniką Bohatera.

## Zarządzanie (admin)
Nic do zarządzania. Opcjonalnie te same agregaty w monitorze kampanii (zakładka Przegląd).

## Dlaczego pasuje do gry
**Wszystkie dane już są w DB**: rzuty w dice/combat events, złoto w logach XP/gold, heksy w `world_hexes` (discovered), tury w `campaign_turns`, gambling w logach tur. To praktycznie SELECT-y z agregacją + jeden ładny ekran. Prawdopodobnie najtańszy feature z całej listy Features.

## Zależności i powiązania
- Brak zależności.
- Baza pod [[Osiągnięcia — kolekcjonerskie]] (te same agregaty, wspólny słownik metryk) i [[Cmentarz bohaterów]].
- Licznik zabójstw per wróg zazębia się z [[Bestiariusz i Atlas Kresów]].

## Out of scope
- Osiągnięcia (osobne issue).
- Porównania między graczami / rankingi.

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1213
