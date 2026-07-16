---
typ: pomysl
status: szkic
zrodlo: "#1216"
---

# Cmentarz bohaterów — nagrobki i epitafia poległych

## Co gracz dostaje
Strona „Polegli" dostępna z ekranu wyboru bohatera: każdy martwy bohater dostaje nagrobek z epitafium generowanym przez LLM w klimacie Kresów. Śmierć permanentna przestaje być tylko stratą — staje się historią. Emocjonalnie mocne, mechanicznie zerowe.

## Jak to działa
- Nagrobek: imię, rasa/archetyp, poziom, dni przeżyte, jak zginął (z ostatniej tury), data śmierci.
- **Epitafium** — jedno-dwa zdania na podstawie Kroniki Bohatera („Tu leży Borys, który przeszedł trzy krainy, a zgubiła go chciwość w krypcie pod Czarnstein"); generowane raz, w momencie śmierci — **regeneracja nie następuje nigdy** (jedno na zawsze).
- Kliknięcie nagrobka → pełna kronika poległego (read-only).
- Technicznie: kolumny w `characters` (`died_at`, `death_cause_text`, `epitaph_text` — preferencja: kolumny zamiast osobnej tabeli); hook w pipeline śmierci bohatera zapisuje przyczynę (snippet ostatniej tury) i generuje epitafium z kroniki. Endpoint `GET /api/users/{id}/graveyard`.

## Zarządzanie (admin)
Nic do zarządzania. Opcjonalnie: podgląd cmentarza per user w sekcji Gracze.

## Dlaczego pasuje do gry
Dane są: status postaci, ostatnia tura, Kronika Bohatera (#1096) z digestem całego życia. Epitafium = jeden tani LLM-call w momencie już obsłużonym przez pipeline śmierci/końca kampanii. Idealnie współgra z „blizną porzucenia" z kroniki.

## Zależności i powiązania
- Kronika Bohatera #1096 — jest.
- Domknięcie tryptyku pamięci bohatera: [[Karta legendy — statystyki bohatera]] (liczniki życia), [[Almanach NPC — spis spotkanych postaci]] (kogo znał), [[Bestiariusz i Atlas Kresów]] (co odkrył).
- Przyszłość: wspólny cmentarz drużyny w multiplayerze (FAZA G) — poza zakresem.

## Out of scope
- Wskrzeszanie / interakcje z poległymi.
- Cmentarz publiczny między userami.

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1216
