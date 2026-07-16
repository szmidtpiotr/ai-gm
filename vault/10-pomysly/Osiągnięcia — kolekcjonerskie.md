---
typ: pomysl
status: szkic
zrodlo: "#1218"
---

# Osiągnięcia — kolekcjonerskie, bez wpływu na balans

## Co gracz dostaje
Osiągnięcia w klimacie Kresów — czysto kolekcjonerskie, **bez nagród mechanicznych** (celowo: zero wpływu na balans). Odblokowanie = toast w grze + wpis na Karcie legendy; postęp częściowy widoczny (np. 34/50 heksów).

## Jak to działa
Przykłady:
- „Pierwsza krew" — pierwsze zabójstwo;
- „Szczęściarz" — 3 Nat 20 w jednej kampanii;
- „Utopione srebro" — przegraj 100 złota w kości;
- „Kartograf" — odkryj 50 heksów;
- „Twardziel" — przeżyj walkę z 1 HP;
- „Legenda Kresów" — ukończ kampanię zwycięstwem.

Technicznie: `game_config_achievements` (key, nazwa, opis, ikona, **warunek jako prosty predykat na agregatach**: metric_key + próg, np. `nat20_per_campaign >= 3`, scope lifetime/campaign, flaga hidden) + `character_achievements` (UNIQUE unlock). Serwis ze słownikiem metryk (metric_key → funkcja agregująca, **współdzielony z legend_stats_service**); check po turze/walce/day-ticku — tani, tylko metryki dotknięte danym eventem; unlock → flaga dla frontendu w odpowiedzi tury. W UI: siatka na Karcie legendy — odblokowane kolorowe, zablokowane szare z paskiem postępu, hidden jako „???".

## Zarządzanie (admin)
- Tabela definicji edytowalna przez Smart Entry / panel Zawartość — dodawanie nowych osiągnięć **bez dotykania kodu**, dopóki metryka istnieje w słowniku.
- Flaga hidden dla niespodzianek; podgląd odblokowań gracza w sekcji Gracze.

## Dlaczego pasuje do gry
Warstwa nad agregatami z Karty legendy — te same liczniki, tylko z progami i toastem. Celowo wydzielone z bestiariusza: bestiariusz nagradza mechanicznie wiedzą łowcy, osiągnięcia są ogólne i czysto ozdobne.

## Liczby startowe
Progi osiągnięć — startowe, swobodnie edytowalne w configu (to treść, nie balans). Seed startowy ~15–20 osiągnięć przez content-as-code (#1202 flow).

## Zależności i powiązania
- **[[Karta legendy — statystyki bohatera]]** (issue siostrzane) — wspólny słownik metryk; wdrażać po niej albo razem.
- Rozgraniczenie z [[Bestiariusz i Atlas Kresów]] — patrz wyżej.

## Out of scope
- Nagrody mechaniczne za osiągnięcia.
- Rankingi między graczami.
- Osiągnięcia multiplayerowe (po FAZIE G).

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1218
