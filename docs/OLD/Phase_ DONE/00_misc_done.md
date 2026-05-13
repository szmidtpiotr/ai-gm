# Różne wdrożenia i poprawki (poza folderami Phase)

**Przeznaczenie:** krótkie wpisy o zmianach, które **nie** mają osobnego folderu `docs/Phase_XX_…/` ani pełnego briefu Perplexity→Cursor — np. synchronizacja dokumentacji, małe hotfixy, porządki w `README`, jednoplikowe aktualizacje.

**Format wpisu** (najnowsze na górze):

```markdown
## YYYY-MM-DD — krótki tytuł
- **Co:** …
- **Dlaczego / kontekst:** …
- **Pliki / obszar:** … (opcjonalnie hash commita)
```

---

## 2026-05-01 — Ustawienia: ukryj mechanikę walki w czacie (panel Walki bez zmian)

- **Co:** Checkbox w sekcji Settings zapisuje `localStorage` (`ai-gm:hideCombatChatBubbles`); gdy włączony, w głównym czacie nie renderują się dymki mechaniki walki (osadzone bloki `__AI_GM_COMBAT_ROLL_V1__`, karty walki użytkownika/wroga, osobny `addGmRollBubble`). Narracja bez bloków walki i rzuty skill (`__AI_GM_ROLL_V1__`) bez zmian; panel Walki i historia „Wyślij ponownie” bez zmian.
- **Dlaczego / kontekst:** Czystszy wąski kanał narracyjny przy zachowaniu pełnej mechaniki w dedykowanym panelu.
- **Pliki / obszar:** `frontend/index.html`, `frontend/js/app.js` (`initCombatChatBubblePref`, `isCombatChatBubbleHidden`), `frontend/js/main.js`, `frontend/js/ui.js` (`addMessage`, `replaceThinkingBubble`, `addGmRollBubble`, `buildInterleavedNarrativeAndCombatHtml`, `renderTurnsToChat`).

## 2026-05-01 — Czat: walka jako zwykły tekst (bez kart roll-card)

- **Co:** Zamiast dymków `roll-card` (obramowanie, DICE, kolorowe stany) mechanika walki (`__AI_GM_COMBAT_ROLL_V1__`, osadzona w narracji, rzuty GM `addGmRollBubble`) wyświetla się w `<pre class="combat-roll-plain">`. Karty `buildRollCardHtml` dla zwykłych skill rolli gracza (`__AI_GM_ROLL_V1__`) bez zmian.
- **Dlaczego / kontekst:** Czystszy kanał narracyjny; mniej „UI walki” w wąskim dymku.
- **Pliki / obszar:** `frontend/js/ui.js` (`buildCombatRollPlainText`, `buildGmRollPlainText`, `addMessage`, `replaceThinkingBubble`, `buildInterleavedNarrativeAndCombatHtml`, `addGmRollBubble`, `renderHistoryPanel`, `isArchiveBubble`), `frontend/styles.css`, `frontend/index.html` (cache-bust `ui.js`).

## 2026-05-01 — Rejest `00_misc_done` + procedura „misc“

- **Co:** Utworzono ten plik jako stałe miejsce na drobne aktualizacje dokumentacji i fixy bez dedykowanej fazy; dopisano wskazanie w `skills/project-memory/SKILL.md` (trigger **update skills**).
- **Dlaczego / kontekst:** Fazy (`Phase_*`) mają własne briefy i prompty; część pracy to pojedyncze poprawki — żeby nie gubiły się w czacie, trafiają tu lub krótko w `skills/DEV_LOG.md`.
- **Pliki / obszar:** `docs/Phase_ DONE/00_misc_done.md`, `skills/project-memory/SKILL.md`.
