<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-05-01 -->

# PROMPT 8H-4 — Katalog Items w Kontekście LLM (Phase 8H)

> Wymaga ukończonych 8H-1 i 8H-2. REV 2 — pełna implementacja na podstawie skanu kodu.

---

## Cel

GM (LLM) nie ma dostępu do listy dostępnych przedmiotów z `game_config_items`, przez co nie może ich wiarygodnie nagradzać przez `Grant Item [label]` ani opisać lootu w narracji. Ten task dodaje:

1. **`get_item_catalog_for_prompt(conn)`** w `combat_service.py` — analogia `get_enemy_catalog_for_prompt` (linia 309)
2. Wstrzyknięcie bloku `[ITEM CATALOG]` do pierwszej wiadomości systemowej w `game_engine.py` — analogia linii 353-355
3. Rozszerzenie `Grant Item` parsera w `turns.py` o lookup `item_key` po labelu z nowego katalogu

---

## Kontekst techniczny

- **Branch:** `develop`
- **NIE ruszać:** `docker-compose.yml` prod, `data/ai_gm.db`, `system_prompt.txt`, inne sekcje game_engine
- **Wzorzec:** `get_enemy_catalog_for_prompt` w `combat_service.py:309` + inject w `game_engine.py:353-355`

### Jak działa wzorzec enemy catalog (do replikacji)

```python
# combat_service.py linia 309:
def get_enemy_catalog_for_prompt(conn: sqlite3.Connection) -> str:
    # SELECT z game_config_enemies WHERE is_active=1
    # Format: "[ENEMY CATALOG]\n- key: label (hp/ac/tier)\n..."
    ...

# game_engine.py linia 350-355:
# enemy_catalog wstrzykiwany gdy NIE MA aktywnej walki (not combat_block)
enemy_catalog = combat_svc.get_enemy_catalog_for_prompt(conn)
if enemy_catalog:
    first["content"] = f"{first.get('content', '').rstrip()}\n\n{enemy_catalog}"
```

> ⚠️ **Korekta względem wcześniejszego opisu:** enemy catalog jest wstrzykiwany przy **braku** aktywnej walki (`not combat_block`), nie przy aktywnej. Item catalog jest wstrzykiwany **zawsze** — również w walce, żeby GM mógł użyć `Grant Item` jako nagrody za walkę.

Blok jest dołączany do `first["content"]` (pierwsza wiadomość systemowa). Mały rozmiar (~10-30 linii).

---

## Implementacja (REV 2)

### Krok 1 — `backend/app/services/combat_service.py`

#### 1a. Nowa funkcja `get_item_catalog_for_prompt`

Dodaj po `get_enemy_catalog_for_prompt` (linia ~340+):

```python
def get_item_catalog_for_prompt(conn: sqlite3.Connection) -> str:
    """
    Buduje blok [ITEM CATALOG] do wstrzyknięcia w system prompt.
    Zawiera tylko itemy is_active=1 AND approved=1.
    Pomija item_type='narrative' (są specyficzne dla kampanii, nie katalogowe).
    """
    rows = conn.execute(
        """
        SELECT key, label, item_type, value_gp,
               effect_type, effect_dice, effect_bonus, effect_target, charges,
               ac_bonus, description
        FROM game_config_items
        WHERE is_active = 1 AND approved = 1
          AND item_type != 'narrative'
        ORDER BY item_type ASC, key ASC
        LIMIT 60
        """
    ).fetchall()

    if not rows:
        return ""

    lines = ["[ITEM CATALOG]"]
    current_type = None
    for r in rows:
        t = str(r["item_type"] or "misc")
        if t != current_type:
            current_type = t
            lines.append(f"  [{t.upper()}]")

        parts = [f"    - {r['key']}: {r['label']}"]

        if t == "armor" and r["ac_bonus"]:
            parts.append(f"(AC +{r['ac_bonus']})")

        if t == "consumable":
            eff = str(r["effect_type"] or "misc")
            dice = str(r["effect_dice"] or "")
            bonus = int(r["effect_bonus"] or 0)
            target = str(r["effect_target"] or "self")
            charges = int(r["charges"] or 1)
            effect_str = eff
            if dice:
                effect_str += f" {dice}"
            if bonus:
                effect_str += f" +{bonus}"
            effect_str += f" [{target}]"
            if charges != 1:
                effect_str += f" x{charges}"
            parts.append(f"({effect_str})")

        if r["value_gp"]:
            parts.append(f"{r['value_gp']} gp")

        lines.append(" ".join(parts))

    return "\n".join(lines)
```

---

### Krok 2 — `backend/app/services/game_engine.py`

Znajdź blok enemy catalog i dodaj item catalog **za nim**, w osobnym bloku `if messages:`:

```python
# Istniejący blok enemy catalog (wstrzykiwany gdy NOT combat_block):
enemy_catalog = combat_svc.get_enemy_catalog_for_prompt(conn)
if enemy_catalog:
    first["content"] = f"{first.get('content', '').rstrip()}\n\n{enemy_catalog}"

# 8H-4: item catalog — zawsze, również przy aktywnej walce
if messages:
    item_catalog = combat_svc.get_item_catalog_for_prompt(conn)
    if item_catalog:
        first["content"] = f"{first.get('content', '').rstrip()}\n\n{item_catalog}"
```

**Kolejność:** enemy catalog (gdy nie ma walki), potem item catalog (zawsze). `first` to `messages[0]`.

---

### Krok 3 — `backend/app/api/turns.py` — Grant Item lookup

`turns.py` ma `GRANT_ITEM_RE` (linia 55) i `parse_grant_item_cue` (linia 786). Po 8H:

- trafienie w katalog `game_config_items` → `grant_loot_to_character(..., [{"item_key": ..., "quantity": 1}], source="gm_grant_item")`
- brak trafienia → `append_narrative_item_to_sheet` (jak dotąd)
- **obie ścieżki** obslużione: zwykła narracja + stream

```python
def _resolve_grant_catalog_item(label: str, conn: sqlite3.Connection) -> dict | None:
    """Exact lower(label), potem LIKE fallback."""
    row = conn.execute(
        """
        SELECT key, label FROM game_config_items
        WHERE lower(label) = lower(?) AND is_active = 1 AND approved = 1
        LIMIT 1
        """,
        (label.strip(),),
    ).fetchone()
    if row:
        return {"item_key": str(row["key"]), "label": str(row["label"])}

    row = conn.execute(
        """
        SELECT key, label FROM game_config_items
        WHERE lower(label) LIKE lower(?) AND is_active = 1 AND approved = 1
        LIMIT 1
        """,
        (f"%{label.strip()}%",),
    ).fetchone()
    if row:
        return {"item_key": str(row["key"]), "label": str(row["label"])}

    return None
```

---

### Krok 4 — Weryfikacja po implementacji

```bash
# Rebuild DEV
docker compose -f docker-compose.dev.yml up -d --build backend
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"

# Rozmiar bloku katalogu:
curl -s http://localhost:8100/api/admin/items | python3 -c "
import json,sys
items=[i for i in json.load(sys.stdin) if i.get('is_active') and i.get('approved') and i.get('item_type')!='narrative']
print(f'{len(items)} aktywnych itemów katalogowych')
"

# Test Grant Item — w grze wpisz:
# 'dostajesz miksturę' → oczekiwanie: inventory item_key=health_potion, consumable_key=NULL
```

---

## Co zostało zrobione *(Cursor)*

- **`combat_service.py`**: `get_item_catalog_for_prompt(conn)` — blok `[ITEM CATALOG]` (aktywne, `approved=1`, bez `narrative`, LIMIT 60, przycinanie ~2000 znaków).
- **`game_engine.py`**: wstrzyknięcie katalogu itemów do pierwszej wiadomości systemowej **zawsze** (również przy aktywnej walce), po bloku enemy catalog.
- **`turns.py`**: `_resolve_grant_catalog_item` (exact + LIKE po `label`); przy `Grant Item` dopasowanie do `game_config_items` → `grant_loot_to_character` z `item_key`, inaczej fallback `append_narrative_item_to_sheet` (stream + zwykła narracja).
- **`loot_service.py`**: grant poza `weapon` zawsze przez **`item_key`**; `_catalog_entry` z `approved=1`.
- **Commit:** `231768e` na `develop` / `origin/develop`.

---

## Notatki po implementacji *(Perplexity)*

**Cel osiągnięty.** GM widzi katalog itemów w każdym proście (niezależnie od walki) i może używać `Grant Item` do przyznawania przedmiotów z bazy.

**Korekta architektoniczna — kiedy jest wstrzykiwany enemy catalog:**
W dokumencie (REV 2) była błędna informacja: enemy catalog jest wstrzykiwany przy **braku** aktywnej walki (`not combat_block`), a nie przy aktywnej. Item catalog jest wstrzykiwany **zawsze** (również w walce) — celowe, żeby GM mógł po walce przyznawać loot przez `Grant Item`. Oba bloki idą do `first["content"]` (system prompt), nie jako osobne wiadomości.

**Grant Item — dwie ścieżki obsłużone:** zwykła narracja i stream. Trafienie w `game_config_items` (exact label lub LIKE) → `item_key` w inventory. Brak trafienia → `narrative_item` w `sheet_json` (stare zachowanie). Podwójna ścieżka jest istotna — stream jest osobną gałęzią w turns.py i miała tendencję do pomijania logiki biznesowej.

**Zakładka Consumables w panelu admin nadal widoczna** — 8H-3 dodało zakładkę `Przedmioty`, ale nie ukryło/nie usunęło `Consumables`. Należy to naprawić w osobnym mini-tasku (wystarczy ukrycie przycisku w `admin.html` lub oznaczenie `deprecated`). Nie blokuje 8H-5.

**Następny krok:** 8H-5 — testy. Commit `231768e` gotowy, można testować.
