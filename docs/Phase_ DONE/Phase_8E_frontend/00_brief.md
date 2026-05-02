<!-- STATUS: DONE -->
<!-- PHASE: 8E | DATE_START: — | DATE_END: — -->

# Phase 8E — Frontend gry (panele, loot, startery) · Brief archiwalny

> Taski: `8E-1` … `8E-5` w tym folderze. Pełne podsumowanie 8E-1 (PR, commity) jest w `8E-1_starter_items.md`.

---

## 1. Cel fazy

Ulepszenie **doświadczenia gracza** przy tworzeniu postaci i w trakcie sesji: starter packs + gold, panele zwijane, panel ekwipunku, popup lootu, lista przedmiotów narracyjnych u GM.

---

## 2. Zakres (komponenty dokumentacji)

| Plik | Temat |
|------|--------|
| `8E-1_starter_items.md` | Archetypy, gold przy tworzeniu, API gold |
| `8E-2_foldable_panels.md` | Panele zwijane w UI |
| `8E-3_inventory_panel.md` | Panel ekwipunku / gold w UI gry |
| `8E-4_loot_popup.md` | Popup po walce / loot |
| `8E-5_gm_items.md` | Przedmioty fabularne u GM |

---

## 3. Osiągnięcia

- Spójny flow: **tworzenie postaci → startowy ekwipunek i GP → widok w UI**.
- Loot i inventory powiązane z Phase 8C i combatem 8A.

---

## 4. Zależności wejściowe

- Phase **8C** (inventory / loot service).  
- Phase **8A** (combat / loot drop) dla 8E-4.

---

## Analiza po fazie *(Perplexity)*

### Ocena implementacji
- **Zgodność z Briefem:** ✅ pełna — 5 tasków pokrywa całą warstwę UX od tworzenia postaci do ekwipunku po walce
- **Pokrycie testami:** głównie weryfikacja manualna + commity z PR w `8E-1`; UI frontend trudny do auto-testów — akceptowalne
- **Ryzyka i dług techniczny:**
  - `characters.gold_gp` wprowadzone w 8E-1 — jedyna kolumna gold; w 8F sklep używa tej kolumny — spójność krytyczna
  - Starter items z archetypów — jeśli archetyp zmieni się (dodanie/usunięcie klucza), starter pack trzeba zaktualizować ręcznie
  - Panel ekwipunku (8E-3) i loot popup (8E-4) bazują na tym samym API inventory — współdzielą ryzyko przy zmianach response shape

### Decyzje przeniesione do kolejnych faz
- **8F** — `gold_gp` z 8E-1 i panel ekwipunku z 8E-3 są fundamentem ekonomii
- **Phase 9 NPC Dialogue** — `8E-5` (przedmioty narracyjne u GM) może zostać rozszerzone o interakcje NPC
- Walidacja starter packów po zmianie archetypów — kandydat na test regresyjny

### STATUS: DONE
