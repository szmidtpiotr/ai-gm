---
typ: pomysl
status: szkic
zrodlo: "#1217"
---

# Kurier Kresowy — gazeta świata

## Co gracz dostaje
Gazeta świata do kupienia w osadzie za drobną opłatę: jednostronicowy numer w stylizowanym layoucie (nagłówki, szpalty, winieta „Kurier Kresowy"). Czasem trafi się wzmianka o czynach samego gracza („Nieznany wędrowiec rozgromił watahę pod Wilczburgiem") — zobaczyć własny wyczyn w gazecie to czysta frajda.

## Jak to działa
- Treść agreguje istniejące systemy: wieści z regionów (wydarzenia), plotki (**w tym fałszywe** — z zachowaniem ich truth_flag!), ogłoszenia (tablica zleceń), wyczyn gracza z Kroniki Bohatera / ostatnich beatów.
- Jeden LLM-call formatuje całość; generacja **lazy** — przy pierwszym zakupie od ostatniej „daty wydania" (np. co N dni świata).
- Akcja gracza: intent „kup gazetę" w osadzie (intent-routing jak akcje karczemne) → potrącenie złota → numer.
- Stare numery zostają w dzienniku (kolekcja); widok stylizowany (serif, szpalty).
- Technicznie: tabela `campaign_newspapers` (numer, data, content_json z sekcjami nagłówek/wieści/plotki/ogłoszenia/wzmianka, tekst wrzutki admina) + `newspaper_service` komponujący numer z danych.

## Zarządzanie (admin)
- Podgląd wygenerowanych numerów per kampania.
- Możliwość dopisania własnej wzmianki do następnego numeru — kanał sterowania graczem, jak ręczne plotki.

## Dlaczego pasuje do gry
To **agregator batchu 2** — nie tworzy nowej treści, skleja istniejącą (eventy + plotki + kontrakty + kronika) w klimatyczny format. Wdrażać dopiero, gdy przynajmniej plotki będą w grze; pełnia smaku przy eventach i zleceniach.

## Liczby startowe
Cena gazety (**1–2 złota**), częstotliwość wydań (co N dni świata), szansa wzmianki o graczu — startowe.

## Zależności i powiązania
- **Miękko blokowane przez [[System plotek w karczmach]]** — bez plotek numer będzie chudy; pełnia przy [[Wydarzenia regionalne]] i [[Tablica zleceń — bounty board]].
- Kronika Bohatera #1096 (jest) — źródło wzmianek o graczu.

## Out of scope
- Gazeta jako źródło questów samych w sobie (od tego są plotki/tablica).
- Wydania PROD-owe / publiczne poza kampanią.

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1217
