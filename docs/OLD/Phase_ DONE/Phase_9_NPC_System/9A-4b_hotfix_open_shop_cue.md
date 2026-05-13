<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# HOTFIX 9A-4b — `Open Shop` cue nie wykrywany (JSON narrative)

> **Typ:** hotfix — brak pytań blokujących (root cause zdiagnozowany)
> **Branch:** `phase-9a-1-npc-schema` (kontynuacja)
> **Plik:** `docs/Phase_9_NPC_System/9A-4b_hotfix_open_shop_cue.md`
> **Zależności:** 9A-4 ✔️

---

## Problem

`Open Shop <npc_key>` nie otwiera modalu sklepu mimo poprawnej implementacji parsera.

**Root cause (zdiagnozowany przez Perplexity):**

GM zwraca odpowiedź jako JSON:
```json
{"narrative": "Aldric krzywi się...", "location_intent": null}
```

`extract_grant_cues(clean_assistant)` jest wywoływane na **surowym JSON stringu** (`clean_assistant = COMBAT_START_RE.sub("", assistant_text)`). Parser szuka `Open Shop` jako ostatniej linii tekstu — ale ostatnia linia JSONa to zawsze `}`. Cue nigdy nie zostaje wykryte.

To samo dotyczy bloku **stream** (linia ~2139) gdzie `extract_grant_cues(clean_text)` ma identyczny problem.

---

## Czego NIE ruszać

- `docker-compose.yml` prod
- `data/ai_gm.db`
- logika `Grant Gold` / `Grant Item` (ta sama naprawa dotyczy ich również — sprawdź czy działają poprawnie po patchu)
- `extract_grant_cues` — sama funkcja jest poprawna, problem w miejscu wywołania

---

## Implementacja (REV 2 — gotowy do wykonania)

> ✅ Cursor implementuje poniższe bez dodatkowych pytań.

### Krok 1 — Pokaż kontekst przed patchem

```bash
sed -n '1590,1605p' /home/piotrszmidt/ai-gm/backend/app/api/turns.py
sed -n '2130,2150p' /home/piotrszmidt/ai-gm/backend/app/api/turns.py
```

Pokaż output przed modyfikacją.

### Krok 2 — Helper `_extract_narrative_for_cues`

Dodaj pomocnik **tuż nad** `extract_grant_cues` (lub na górze pliku obok innych helperów):

```python
def _extract_narrative_for_cues(text: str) -> tuple[str, dict | None]:
    """
    Jeśli text jest JSON-em z polem 'narrative' — zwraca (narrative, parsed_dict).
    W przeciwnym razie zwraca (text, None) — fallback do plain text.
    """
    try:
        parsed = json.loads(_strip_json_code_fence(text))
        if isinstance(parsed, dict) and "narrative" in parsed:
            return str(parsed.get("narrative") or ""), parsed
    except (ValueError, TypeError):
        pass
    return text, None


def _repack_narrative(original_text: str, narrative: str, parsed: dict | None) -> str:
    """
    Wstawia oczyszczone narrative z powrotem do JSON (jeśli był JSON)
    lub zwraca narrative bezpośrednio (plain text).
    """
    if parsed is None:
        return narrative
    try:
        parsed["narrative"] = narrative
        return json.dumps(parsed, ensure_ascii=False)
    except Exception:
        return narrative
```

### Krok 3 — Patch miejsca sync (linia ~1595)

Zamień:
```python
clean_assistant = COMBAT_START_RE.sub("", assistant_text).rstrip()
clean_assistant, grant_item_label, grant_gold_amount, open_shop_npc_key = extract_grant_cues(clean_assistant)
```

Na:
```python
clean_assistant = COMBAT_START_RE.sub("", assistant_text).rstrip()
_narrative_for_cues, _parsed_json = _extract_narrative_for_cues(clean_assistant)
_narrative_for_cues, grant_item_label, grant_gold_amount, open_shop_npc_key = extract_grant_cues(_narrative_for_cues)
clean_assistant = _repack_narrative(clean_assistant, _narrative_for_cues, _parsed_json)
```

### Krok 4 — Patch miejsca stream (linia ~2139)

Znajdź analogiczne wywołanie `extract_grant_cues(clean_text)` w bloku stream.

Zamień wzorzec:
```python
clean_text, grant_item_label, grant_gold_amount, open_shop_npc_key = extract_grant_cues(clean_text)
```

Na:
```python
_narrative_for_cues_s, _parsed_json_s = _extract_narrative_for_cues(clean_text)
_narrative_for_cues_s, grant_item_label, grant_gold_amount, open_shop_npc_key = extract_grant_cues(_narrative_for_cues_s)
clean_text = _repack_narrative(clean_text, _narrative_for_cues_s, _parsed_json_s)
```

> **Uwaga:** Ten sam wzorzec dotyczy `Grant Gold` i `Grant Item` — są naprawiane automatycznie tym samym patchem (działają przez `extract_grant_cues`).

### Krok 5 — Weryfikacja

```bash
cd /home/piotrszmidt/ai-gm
docker compose -f docker-compose.dev.yml up -d --build backend
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"

# Uruchom turę z tekstem inicjującym sklep
# Sprawdź logi czy pojawia się open_shop_npc_key
docker logs ai-gm-dev-backend-1 --tail=30 | grep -i "open_shop\|shop\|grant"
```

### Krok 6 — Test jednostkowy

Dodaj do `backend/tests/test_phase9a_shop.py`:

```python
def test_open_shop_cue_detected_in_json_narrative():
    """
    extract_grant_cues NIE wykrywa cue w JSON — _extract_narrative_for_cues musi
    wyciągnąć narrative przed parsowaniem.
    """
    import json
    from app.api.turns import _extract_narrative_for_cues, extract_grant_cues, _repack_narrative

    raw = json.dumps({"narrative": "Aldric kiwa głową.\nOpen Shop merchant_aldric",
                      "location_intent": None}, ensure_ascii=False)
    narrative, parsed = _extract_narrative_for_cues(raw)
    clean, _, _, shop_key = extract_grant_cues(narrative)
    result = _repack_narrative(raw, clean, parsed)

    assert shop_key == "merchant_aldric"
    assert "Open Shop" not in json.loads(result)["narrative"]


def test_grant_gold_cue_detected_in_json_narrative():
    import json
    from app.api.turns import _extract_narrative_for_cues, extract_grant_cues, _repack_narrative

    raw = json.dumps({"narrative": "Oto twoja nagroda.\nGrant Gold 50",
                      "location_intent": None}, ensure_ascii=False)
    narrative, parsed = _extract_narrative_for_cues(raw)
    clean, _, gold, _ = extract_grant_cues(narrative)
    assert gold == 50
    assert "Grant Gold" not in json.loads(_repack_narrative(raw, clean, parsed))["narrative"]
```

Uruchom:
```bash
docker compose -f docker-compose.dev.yml exec -T backend python3 -m pytest \
  tests/test_phase9a_shop.py -v -k "json_narrative"
```

---

## Co zostało zrobione *(uzupełnia Cursor)*

- Pokazano kontekst przed patchem (`create_turn` i `create_turn_stream`) — wywołania `extract_grant_cues(...)` działały na całym JSON stringu.
- W `backend/app/api/turns.py` dodano helpery:
  - `_extract_narrative_for_cues(text)` — wyciąga `narrative` z JSON odpowiedzi (fallback: plain text),
  - `_repack_narrative(... )` — pakuje oczyszczone `narrative` z powrotem do JSON.
- Zmieniono oba miejsca wywołań cue parsera:
  - sync (`create_turn`) — cue parsing działa na `narrative`, potem repack do JSON,
  - stream (`create_turn_stream`) — analogiczny patch.
- Dzięki temu hotfix naprawia jednocześnie wykrywanie `Open Shop`, `Grant Gold` i `Grant Item` dla odpowiedzi JSON-mode.
- Dodano testy regresyjne do `backend/tests/test_phase9a_shop.py`:
  - `test_open_shop_cue_detected_in_json_narrative`,
  - `test_grant_gold_cue_detected_in_json_narrative`.
- Weryfikacja:
  - wykonano rebuild backendu: `docker compose -f docker-compose.dev.yml up -d --build backend`,
  - healthcheck: `GET /api/healthz` -> `{"status":"ok"}`,
  - testy: `pytest tests/test_phase9a_shop.py -v -k "json_narrative"` -> **2 passed**.

---

## Notatki po implementacji *(uzupełnia Perplexity)*

*(Perplexity uzupełni po raporcie Cursora)*
