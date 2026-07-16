---
typ: pomysl
status: szkic
zrodlo: "#1198"
---

# Kapliczki przydrożne i błogosławieństwa

## Co gracz dostaje
Na heksach traktów stoją kapliczki przydrożne — bardzo kresowy klimat (rozstaje, święte dęby, kamienne baby). Podróżując przez heks z kapliczką gracz może się zatrzymać, złożyć ofiarę i dostać drobne, jednorazowe błogosławieństwo. Albo… spróbować kapliczkę okraść.

## Jak to działa
- **Ofiara** (grosz, chleb, modlitwa — gracz wybiera tekstem, intent-routing rozpoznaje) daje jednorazowe błogosławieństwo:
  - przerzut jednego dowolnego rzutu (trzymane do użycia),
  - +1 do następnego testu,
  - ochrona przed najbliższą zasadzką (pierwszy ambush-encounter pominięty).
- Błogosławieństwa **nie kumulują się** — max 1 aktywne; trzymane w `sheet_json` bohatera (`active_blessing`).
- **Profanacja lub chciwość** (okradzenie kapliczki) → drobna klątwa z systemu klątw.
- Rzadko (mała waga) kapliczka **„dziwna"** — coś tu nie gra, opcjonalny mikro-wątek (hook do plotki/kontraktu/skarbu).
- Technicznie: osobna tabela `world_shrines` (heks, typ, stan normal/strange/desecrated) + `game_config_blessings` (pula efektów z wagami); detekcja kapliczki hookiem w travel (jak encountery), konsumpcja efektu w skill_router (przerzut/+1) i w encounter roll (ochrona). W UI: ikona błogosławieństwa przy pasku kondycji (złota ramka), przycisk „użyj przerzutu" przy karcie rzutu.
- **UWAGA seeding**: `world_hexes` map_level=0 należy do Piotra — kapliczki jako osobna tabela, NIE edycja world_hexes; rozmieszczenie na mapie Kresów do akceptacji Piotra przed seedem.

## Zarządzanie (admin)
- Kapliczki jako obiekty na heksach (wzór: sub-lokacje/POI) — warstwa w zakładce Mapa (toggle), klik na heks → dodaj/edytuj/usuń kapliczkę, typ.
- Pula błogosławieństw i typów kapliczek w tabeli configu; waga „dziwnych" tuningowalna.

## Dlaczego pasuje do gry
**Najtańszy feature z całej listy**, a mocno buduje tożsamość świata — słowiańsko-germańskie Kresy z kapliczkami na rozstajach to dokładnie ten klimat (konwencja nazewnicza #997). Mechanicznie: pierwsze źródło „consumable buff" poza miksturami, reuse systemu klątw.

## Liczby startowe
- Gęstość kapliczek: **~1 na 6–8 heksów traktu**
- Waga „dziwnych": **5%**
- Szansa klątwy przy profanacji: **100%** — profanacja ma boleć.

## Zależności i powiązania
- Travel/heksy i intent-routing — są.
- [[Klątwy i trofea z krytyków]] — **miękka zależność**: profanacja może początkowo dawać zwykły debuff-condition, prawdziwa klątwa po wdrożeniu #1194.
- „Dziwne" kapliczki generują hooki do [[System plotek w karczmach]] i [[Tablica zleceń — bounty board]].

## Out of scope
- Bóstwa/religie jako system (frakcje wiary) — dużo większy temat, v2.
- Kapliczki na mapach lokalnych (FAZA ML) — v2.

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1198
