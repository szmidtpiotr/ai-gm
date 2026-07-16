---
typ: pomysl
status: szkic
zrodlo: "#1214"
---

# Almanach NPC — spis spotkanych postaci

## Co gracz dostaje
Automatyczny spis postaci spotkanych w kampanii: kto, gdzie, kiedy, z jakim nastawieniem — plus „ostatnia rozmowa" w jednym zdaniu („obiecałeś mu odnaleźć syna"). Rozwiązuje realny problem grania w odcinkach z przerwami: „kim był ten Bogumił, któremu coś obiecałem?".

## Jak to działa
Każdy wpis zawiera:
- kto (imię, rola), gdzie spotkany (lokacja), kiedy (dzień wyprawy);
- nastawienie/relacja (feed z systemu reputacji/attitude NPC);
- **„ostatnia rozmowa"** — jedno zdanie z podsumowań tur;
- otwarte obietnice/wątki z tym NPC, jeśli wykrywalne z questów.

Technicznie: tabela `campaign_npc_log` (UNIQUE campaign+npc, lokacja i dzień pierwszego spotkania, ostatnie podsumowanie interakcji, attitude, notka admina). Hook w pipeline podsumowań tur: gdy tura dotyczy NPC → upsert wpisu; extract „ostatniej rozmowy" jako dopisek do istniejącego promptu podsumowań — **bez dodatkowego wywołania LLM**. W UI gracza: zakładka „Postacie" w dzienniku — lista kart NPC.

## Zarządzanie (admin)
Karmi się z istniejącego trackingu NPC i podsumowań tur — zero ręcznej pracy. Admin może w panelu Świat → NPC dopisać/skorygować notkę widoczną w almanachu gracza (np. sprostować przekłamane podsumowanie).

## Dlaczego pasuje do gry
NPC są już trackowane (tabele NPC + occurrences w turach), podsumowania tur już powstają (summaries service). Almanach to widok + jedna tabela wiążąca + tani LLM-extract. Gracz, który pamięta NPC, gra głębiej — QoL, który realnie podnosi jakość narracji.

## Zależności i powiązania
- Brak twardych zależności.
- Synergia z Kroniką Bohatera (#1096) — NPC znani z poprzednich kampanii mogą być oznaczeni „stary znajomy".
- Siostrzana kolekcja pamięci obok [[Bestiariusz i Atlas Kresów]] i [[Karta legendy — statystyki bohatera]]; kronika poległego widoczna też na [[Cmentarz bohaterów]].

## Out of scope
- Pełne drzewo relacji NPC↔NPC.
- Almanach cross-kampanijny (v2, przez kronikę).

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1214
