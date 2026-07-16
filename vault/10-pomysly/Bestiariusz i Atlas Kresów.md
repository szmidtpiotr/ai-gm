---
typ: pomysl
status: szkic
zrodlo: "#1191"
---

# Bestiariusz i Atlas Kresów — kolekcje odkryć

## Co gracz dostaje
Dwie kolekcje: **Bestiariusz** — każdy pokonany typ wroga odblokowuje wpis z opisem, słabościami i ilustracją (portrety generowane FLUX-em, jak w #171/#172); oraz **Atlas Kresów** — odkryte lokacje, przebyte heksy i potwierdzone plotki budują statystyki eksploracji bohatera.

## Jak to działa
- Progresja wiedzy w bestiariuszu: **1. zabójstwo** → wpis podstawowy (nazwa, opis); **5 zabójstw** danego typu → „wiedza łowcy": +1 do trafienia na ten typ **albo** podgląd HP wroga w walce (jedna z dwóch opcji, nie obie — decyzja przy wdrożeniu).
- Atlas jest **cross-kampanijny** per bohater, spójnie z modelem Hero-First.
- Zamknięte wpisy widoczne jako sylwetki „???" — siatka kart w karcie postaci.
- Technicznie: tabela `character_bestiary` (liczniki zabójstw per typ wroga, progi odblokowań), hook w `combat_service` na śmierć wroga, bonus „wiedza łowcy" doliczany w `resolve_attack` analogicznie do proficiency. Atlas to agregaty z `world_hexes` (discovered) + lokacje + plotki.

## Zarządzanie (admin)
Prawie zero nowej treści: bestiariusz karmi się z `game_config_enemies` (ewentualnie nowe pole `lore_text`, które Smart Entry umie generować); ilustracje batch-gen przez istniejący pipeline obrazków. Opcjonalnie % kompletności kolekcji gracza w monitorze kampanii.

## Dlaczego pasuje do gry
Kolekcjonerski dopamine-loop prawie za darmo. Mechanicznie wzmacnia farmienie lochów (powód, żeby wracać po komplet wpisów). Dane o zabójstwach już płyną przez combat pipeline — trzeba je tylko zliczać.

## Liczby startowe
- Próg wiedzy łowcy: **5 zabójstw**
- Wielkość bonusu: **+1** — tuning w Sandboxie.

## Zależności i powiązania
- Brak twardych zależności; Atlas zyskuje na FAZA RM (regiony jako kategorie kolekcji) — nie blokująca.
- Pokrewne kolekcje pamięci bohatera: [[Almanach NPC — spis spotkanych postaci]], [[Karta legendy — statystyki bohatera]] (najczęściej zabijany wróg czerpie z tych samych liczników), [[Cmentarz bohaterów]].
- [[Osiągnięcia — kolekcjonerskie]] celowo wydzielone: bestiariusz nagradza mechanicznie wiedzą łowcy, osiągnięcia są czysto ozdobne.

## Out of scope
- Osiągnięcia/achievementy ogólne (osobny temat — patrz wyżej).
- Handel wiedzą (sprzedaż wpisów uczonym) — v2.

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1191
