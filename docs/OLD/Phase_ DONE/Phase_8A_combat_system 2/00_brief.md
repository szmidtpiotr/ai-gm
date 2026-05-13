<!-- STATUS: DONE -->
<!-- PHASE: 8A | DATE_START: — | DATE_END: — -->

# Phase 8A — Combat System 2.0 (backend / silnik) · Brief archiwalny

> **Kanoniczna nazwa folderu:** `Phase_8A_combat_system 2` (duplikat `Phase 8A - combat system 2` usunięty — treść była identyczna).  
> **Relacja z Phase 8B:** **8A** = migracje, `active_combat`, rozstrzyganie ataków, API, loot po walce, śmierć — **w backendzie**. **8B** = animacje, overlaye, HP bar — **w frontendzie** (osobny folder).

---

## 1. Cel fazy

Nowy silnik walki: wykrycie starcia, inicjatywa, tury, rozstrzyganie trafień/obrażeń, koniec walki (loot, śmierć), integracja z inventory/loot.

**DoD (archiwum):**
- [x] Migracja DB (`active_combat` i powiązania — wg promptów PROMPT 1–6 i kroków `step_*`)
- [x] Endpointy i logika resolve attack / tury
- [x] Integracja loot ze śmiercią wroga (`loot_service`)
- [x] Ŝieżki testów i e2e checklist w dokumentacji fazy

---

## 2. Zakres dokumentacji w folderze

| Obszar | Opis |
|--------|------|
| PROMPT 1–6 | Migracja, AC, resolve_attack, API, dymki, testy |
| `Implementacja part 1/` | Kroki `step_1.1` … `step_8.x` — sekwencyjna implementacja |
| `e2e_checklist.md` | Lista kontrolna E2E |

---

## 3. Osiągnięcia (streszczenie)

- Spójny **pipeline walki** od `[COMBAT_START]` przez tury gracza/wroga do końca walki i lootu.
- Oddzielenie **Combat backend** od **Combat UX** (faza 8B).

---

## 4. Powiązane fazy

- **Phase 8C** — inventory / grant loot (konsumuje wyniki walki).  
- **Phase 8B** — polish UI combatu.  
- **Phase 8E** — loot popup / panel gracza.

---

## Podsumowanie wdrożenia *(Cursor / zespół)*

Szczegóły commitów i acceptance były raportowane per krok w plikach `step_*.txt` i `PROMPT *.md`.

---

## Analiza po fazie *(Perplexity)*

### Ocena implementacji
- **Zgodność z Briefem:** ✅ pełna — silnik walki w backendzie zrealizowany kompletnie, rozdzielony od UI (8B)
- **Pokrycie testami:** E2E checklist + testy per krok w `step_*.txt`; brak scentralizowanego pliku pytest na poziomie fazy — warto uzupełnić w przyszłych fazach
- **Ryzyka i dług techniczny:**
  - `active_combat` jako tabela — potencjalny bottleneck przy wielu równoległych sesjach (nie dotyczy MVP)
  - Loot po walce przez `grant_loot_to_character` — współdzielony z 8C/8E/8F — zmiana sygnatury wymaga aktualizacji we wszystkich konsumentach

### Decyzje przeniesione do kolejnych faz
- **8B** — cała warstwa UI/UX walki
- **8C** — ujednolicony model inventory konsumujący loot z 8A
- Fallback dla `active_combat` przy crash kontenera — do rozważenia w fazie stabilizacji

### STATUS: DONE
