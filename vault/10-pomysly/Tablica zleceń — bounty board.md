---
typ: pomysl
status: szkic
zrodlo: "#1189"
---

# Tablica zleceń — bounty board w osadach

## Co gracz dostaje
W każdej większej osadzie (lokacja z tagiem osady / safe_for_rest) wisi tablica z 2–3 aktywnymi kontraktami: „Wilki nękają gospodarstwo pod Wilczburgiem" (łowiecki), „Zaginął kupiec na trakcie do Wachstein" (śledztwo/eskorta), „Dostarcz paczkę do młyna przed zmrokiem" (dostawa z limitem czasu z systemu podróży). Krótkie, samodzielne przygody do wzięcia „od ręki".

## Jak to działa
- Kontrakt jest **krótki (1–3 sceny)** i niezależny od głównego planu GM — nie dotyka `gm_plan_json`.
- Nagroda: złoto + reputacja regionu (istniejący system reputacji per-region, #1099).
- Tablica odświeża się na cooldownie (mechanizm jak `character_dungeon_runs`).
- Gracz może mieć ograniczoną liczbę aktywnych kontraktów naraz.
- Kontrakty wypełniają pustkę „pomiędzy" beatami kampanii — dziś jedynym farmable contentem są lochy.
- Technicznie: tabela szablonów `game_config_contract_templates` (typ, wzorzec tytułu, beaty, widełki nagród, cooldown) + `character_contracts` (stan, wygenerowana treść, termin). LLM losuje szablon i ubiera go w lokalny kontekst: nazwy z okolicznych heksów, NPC z regionu, aktualne wydarzenia. Progres kontraktu śledzony hookiem w pipeline tury (analogicznie do beatów questów), rozliczenie automatyczne.

## Zarządzanie (admin)
- Tabela szablonów kontraktów (łowiecki / eskorta / dostawa / śledztwo) — edycja w Kuźni lub przez Smart Entry.
- Monitor kampanii pokazuje, jakie kontrakty gracz przyjął i w jakim są stanie.

## Dlaczego pasuje do gry
Travel system (FAZA PT), reputacja regionalna i infrastruktura cooldownów już istnieją — to w ~80% sklejenie gotowych klocków. Naturalny kanał dystrybucji: [[System plotek w karczmach]].

## Liczby startowe
- Limit aktywnych kontraktów naraz: **2**
- Cooldown tablicy i widełki nagród — wartości startowe, tuning po smoke teście.

## Zależności i powiązania
- Reputacja regionalna #1099 (już jest).
- Synergia (nie blokująca): [[System plotek w karczmach]] i [[Wydarzenia regionalne]] mogą wskazywać kontrakty; kontrakty trafiają też do ogłoszeń w [[Kurier Kresowy — gazeta świata]].
- Mini-quest zdejmujący klątwę z [[Klątwy i trofea z krytyków]] może korzystać z tej infrastruktury.

## Out of scope
- Kontrakty frakcyjne (czekają na per-frakcja rep #1103).
- Kontrakty multiplayer.

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1189
