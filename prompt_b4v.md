Wykonujesz B4V — celowaną weryfikację Bloku 4 FAZY U gry AI-GM (sklep + trwałość + przedmiot).
To NIE jest pełny game-smoke i NIE zadanie /tdd — to jeden ukierunkowany playtest z dowodami.

Przeczytaj najpierw:
1. CLAUDE.md (zasady projektu i środowiska),
2. notes.md → sekcja "🎯 Weryfikacja Bloku 4 (celowana)" (kontekst i kryterium zaliczenia).

DLACZEGO: od smoke'a U32b przeszedł cały Blok 4 bez playtestu — unifikacja przedmiotów
(3 tabele → game_items), dual-write, aktywacja trwałości (#467), nowy sklep (U16). Żółta flaga:
18 czerwonych testów shop/loot/inventory z U11c (#557/#558). Sprawdzamy, czy gra w tym obszarze
faktycznie działa dla gracza — nie czy endpoint odpowiada.

KONTRAKT (jak /game-test-player-screenshot):
- Weryfikacja TYLKO przez realne tury gry na koncie Demo (user_id=1). Nigdy user_id=1013.
- Tylko DEV (.61). Nigdy PROD. SQL wyłącznie do ODCZYTU, przez SSH+docker exec (nigdy sshfs).
- Kampanii i bohatera po teście NIE usuwać.
- Najpierw upewnij się, że backend na .61 jest aktualny (Blok 4 + U16 zacommitowane i zbudowane
  `--build`). Jeśli nie — zbuduj, inaczej testujesz stary kod.

UŻYJ skilla /game-test-player-screenshot. Scenariusz (3 mechaniki Bloku 4, każda z DOWODEM):

1. SKLEP (zmiana złota):
   - Otwórz sklep w grze, kup 1 przedmiot i sprzedaj 1 przedmiot.
   - Dowód: zrzut karty/modala sklepu z ceną + saldem złota PO; SQL złota przed/po
     (`json_extract(sheet_json,'$.gold')` w characters) = cena z katalogu. Screenshot PRZED i PO.
2. TRWAŁOŚĆ (durability):
   - Sprawdź, że założona broń/zbroja ma pasek trwałości (np. 100/100) w karcie/ekwipunku.
   - Stocz walkę; po walce trwałość ma SPAŚĆ.
   - Dowód: zrzut paska przed walką + po; SQL `durability_current`/`durability_max`
     w character_inventory przed/po.
3. PRZEDMIOT Z game_items (unifikacja + loot):
   - Zdobądź przedmiot (loot z walki albo zakup) i potwierdź, że trafia do ekwipunku.
   - Dowód: SQL — wiersz w character_inventory z ustawionym `game_item_key`; przedmiot
     widoczny w ekwipunku w UI (zrzut).

LIMITY: maks. 15 tur. Rate limit (502) → czekaj 60 s; model gpt-4.1-mini w configu kampanii.
gate no_enemies przy "atakuję" → wystartuj walkę przez /combat/start (token z dev-login) —
procedura w SKILL.md /game-test-player-screenshot, sekcja Gotchas.

DEFEKTY: każdy ❌ z trzech mechanik = `gh issue create` tytuł "[BUG] B4V — <opis>",
labels: bug + needs-testing, body: oczekiwane vs faktyczne + SQL/screenshot + tura.
Priorytet w tytule (P0 blokuje grę / P1 psuje doświadczenie / P2 kosmetyka).

STOP. Raport końcowy po polsku, prostym językiem:
- werdykt: Blok 4 OK / Blok 4 z defektami (lista #),
- 3 mechaniki: ✅/❌ każda z jednym zdaniem dowodu (cytat SQL lub co widać na zrzucie),
- 3+ zrzuty z opisem (PRZED/PO sklepu, pasek trwałości, ekwipunek),
- co następne: "wracaj do prompt.md → U24" (jeśli OK) albo "najpierw napraw defekty B4V przed U27".

Zaktualizuj notes.md: [x] przy B4V + werdykt + linki do ewentualnych issues.
Zacznij od sprawdzenia stanu backendu na .61.
