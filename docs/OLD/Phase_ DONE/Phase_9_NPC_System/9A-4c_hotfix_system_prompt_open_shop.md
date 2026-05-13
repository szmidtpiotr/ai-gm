<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# HOTFIX 9A-4c — system_prompt: `Open Shop` za mało deterministyczny

> **Typ:** hotfix systemu promptów + hotfix parsera (9A-4b) — dwa patche w jednym
> **Branch:** `phase-9a-1-npc-schema` (kontynuacja)
> **Zależności:** 9A-4 ✔️, 9A-4b (parser JSON) — oba patche razem

---

## Problem

**Diagnoza z logów (tura 21):**

Gracz napisał `"pokaż co masz do sprzedania"` — GM odpowiedział narracyjnie (opisał towar Aldrica), ale **nie użył cue `Open Shop`**. Aktualna reguła jest zbyt ogólna:

```
# AKTUALNA (za słaba):
- Gdy gracz chce handlować z NPC-merchantem, zakończ odpowiedź OSTATNIĄ linią:
  Open Shop <npc_key>
```

GM zinterpretował `"pokaż co masz"` jako rozmowę, nie jako inicjowanie handlu.

**Drugi problem (9A-4b):** nawet gdyby GM dodał cue, parser `extract_grant_cues` szuka go w surowym JSON stringu (ostatnia linia to `}`), nie w polu `narrative`. Oba patche są potrzebne.

---

## Czego NIE ruszać

- `docker-compose.yml` prod
- `data/ai_gm.db`
- Inne sekcje `system_prompt.txt`
- Logika `Grant Gold` / `Grant Item`

---

## Implementacja

### Patch A — `backend/prompts/system_prompt.txt`

Znajdź sekcję `## SKLEP NPC (OPEN SHOP)` i zamień całą sekcję na:

```
## SKLEP NPC (OPEN SHOP)
- Gdy gracz wykonuje DOWOLNĄ z poniższych akcji wobec NPC-merchanta:
  pokaż towar / chcę kupić / co masz / ile kosztuje / handlować / sklep / towary / kupuję
  → zakończ odpowiedź OSTATNIĄ linią (nic po niej):
  Open Shop <npc_key>
- Przykład: Open Shop merchant_aldric
- Używaj WYŁĄCZNIE dla NPC typu merchant z is_shop=1.
- Cue musi być absolutnie ostatnią linią — żaden tekst po niej.
- Nie używaj jeśli gracz tylko rozmawia z merchantem bez zamiaru zakupu.
```

Pokaż diff przed zapisem.

### Patch B — `backend/app/api/turns.py` (parser JSON — z 9A-4b)

Dodaj dwa helpery przed lub obok `extract_grant_cues`:

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

**Patch sync** — linia ~1595, zamień:
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

**Patch stream** — znajdź analogiczne `extract_grant_cues(clean_text)` w bloku stream (~linia 2139), zamień identycznie:
```python
_narrative_for_cues_s, _parsed_json_s = _extract_narrative_for_cues(clean_text)
_narrative_for_cues_s, grant_item_label, grant_gold_amount, open_shop_npc_key = extract_grant_cues(_narrative_for_cues_s)
clean_text = _repack_narrative(clean_text, _narrative_for_cues_s, _parsed_json_s)
```

Pokaż diff `turns.py` przed zapisem.

### Patch C — Testy

Dodaj do `backend/tests/test_phase9a_shop.py`:

```python
def test_open_shop_cue_detected_in_json_narrative():
    import json
    from app.api.turns import _extract_narrative_for_cues, extract_grant_cues, _repack_narrative

    raw = json.dumps({
        "narrative": "Aldric kiwa głową.\nOpen Shop merchant_aldric",
        "location_intent": None
    }, ensure_ascii=False)

    narrative, parsed = _extract_narrative_for_cues(raw)
    clean, _, _, shop_key = extract_grant_cues(narrative)
    result = _repack_narrative(raw, clean, parsed)

    assert shop_key == "merchant_aldric"
    assert "Open Shop" not in json.loads(result)["narrative"]


def test_grant_gold_cue_detected_in_json_narrative():
    import json
    from app.api.turns import _extract_narrative_for_cues, extract_grant_cues, _repack_narrative

    raw = json.dumps({
        "narrative": "Oto twoja nagroda.\nGrant Gold 50",
        "location_intent": None
    }, ensure_ascii=False)

    narrative, parsed = _extract_narrative_for_cues(raw)
    clean, _, gold, _ = extract_grant_cues(narrative)
    assert gold == 50
    assert "Grant Gold" not in json.loads(_repack_narrative(raw, clean, parsed))["narrative"]
```

### Weryfikacja

```bash
cd /home/piotrszmidt/ai-gm

# Rebuild backend
docker compose -f docker-compose.dev.yml up -d --build backend
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"

# Testy
docker compose -f docker-compose.dev.yml exec -T backend python3 -m pytest \
  tests/test_phase9a_shop.py -v -k "json_narrative"

# Sprawdź sekcję w system_prompt
grep -A 8 "SKLEP NPC" backend/prompts/system_prompt.txt
```

Potem zagraj turę z tekstem `"pokaż co masz do sprzedania"` i wklej logi.

---

## Co zostało zrobione *(uzupełnia Cursor)*

- Wdrożono hotfix sekcji `## SKLEP NPC (OPEN SHOP)` w `backend/prompts/system_prompt.txt`:
  - rozszerzono trigger na konkretne intencje zakupowe (`pokaż towar`, `co masz`, `ile kosztuje`, `kupię`, itd.),
  - doprecyzowano, że cue ma być absolutnie ostatnią linią,
  - doprecyzowano ograniczenie do merchantów z `is_shop=1`.
- Hotfix parsera JSON z 9A-4b jest obecny i aktywny w `backend/app/api/turns.py`:
  - `_extract_narrative_for_cues(...)`,
  - `_repack_narrative(...)`,
  - parsowanie cue działa na `narrative` w sync i stream.
- Weryfikacja wykonana:
  - rebuild backend: `docker compose -f docker-compose.dev.yml up -d --build backend`,
  - healthcheck: `GET /api/healthz` -> `{"status":"ok"}`,
  - testy regresyjne JSON-narrative:
    `pytest tests/test_phase9a_shop.py -v -k "json_narrative"` -> **2 passed**.
- Potwierdzono obecność nowej sekcji promptu (`SKLEP NPC`) przez odczyt zawartości pliku.

---

## Notatki po implementacji *(uzupełnia Perplexity)*

*(Perplexity uzupełni po raporcie Cursora)*
