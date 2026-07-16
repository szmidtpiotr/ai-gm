---
typ: pomysl
status: szkic
zrodlo: "#1215"
---

# Szybkie akcje — kontekstowe chipy pod composerem

## Co gracz dostaje
Pod polem tekstowym pojawiają się 2–3 kontekstowe chipy szybkich akcji: „Przeszukaj ciała" (po walce), „Porozmawiaj z karczmarzem" (w karczmie), „Ruszaj do Wachstein" (przy trakcie). Tap = wysłanie akcji jak zwykłej tury. Największy skok wygody na telefonie — pisanie na mobile to główny friction gry tekstowej.

## Jak to działa
- Chip to skrót, nie osobna mechanika; zawsze można pisać własny tekst — chipy nigdy nie zastępują inputu.
- Sugestie generowane w **tym samym wywołaniu LLM co narracja** (pole `suggested_actions`, max 3 stringi w structured output) — NIE osobny call.
- Twardy filtr: odrzucane sugestie zawierające słowa kluczowe testów/zagadek.
- Fallback deterministyczny, gdy LLM nie zwróci sugestii: reguły (po walce → „Przeszukaj ciała", w osadzie → „Idź do karczmy", niski HP → „Odpocznij").

**Zabezpieczenia designowe (ważne):**
- celowo 2–3 chipy, nie 6 — mają podpowiadać oczywistości, nie wyręczać z wymyślania;
- **nigdy nie sugerować rozwiązania zagadki, testu ani decyzji fabularnej** — tylko akcje „oczywiste w scenie" (ruch, rozmowa, przeszukanie, odpoczynek);
- wyłączalne per użytkownik (część graczy woli czysty tekst).

**Ryzyko**: railroading — gracz przestaje wymyślać własne akcje. Mitygacja: limity powyżej + obserwacja po wdrożeniu (odsetek tur z chipa vs pisanych — mierzalne z logów tur).

## Zarządzanie (admin)
- Przełącznik globalny + per-user (ustawienia gracza).
- Tuning liczby chipów i reguł generowania w ustawieniach systemowych.

## Dlaczego pasuje do gry
Narrator i tak zna scenę (lokacja, obecni NPC, stan walki, sąsiednie heksy) — generowanie 2–3 sensownych akcji to tani dopisek do istniejącego wywołania narracji.

## Liczby startowe
- Liczba chipów: **3** — wartość startowa.

## Zależności i powiązania
Brak — samodzielny feature czysto UI/UX.

## Out of scope
- Chipy akcji bojowych (walka ma już swój pasek akcji — Faza SF).
- Podpowiedzi „co dalej w fabule".

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1215
