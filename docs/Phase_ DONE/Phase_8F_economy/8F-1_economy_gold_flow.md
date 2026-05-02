<!-- STATUS: DONE (value_gp + filtr sklepu) -->
<!-- REV: 3 | DATE: 2026-04-29 -->

# PROMPT 8F-1 — Economy: Gold flow, sklep NPC, `value_gp` w katalogach

> **Workflow:** Perplexity REV 1 → Cursor odpowiada → Perplexity REV 2 → Cursor implementuje.
> **Notion:** https://www.notion.so/Phase-8F-Economy-34e8842467a880c092e5fcae8cfd340f
> **Warunek wstępny:** Phase 9 NPC (`is_shop`, `shop_inventory_json`) — spełniony w kodzie.
> **Branch roboczy:** `phase-8f-1-economy-gold-flow` (opcjonalnie; merge przez `develop`)

---

## Kontekst (potwierdzony)

- Tabela `npcs` ma `is_shop` i `shop_inventory_json` ✅
- `characters.gold_gp` istnieje (migration admin) ✅
- `GET/POST /api/characters/{id}/gold` w `backend/app/api/inventory.py` ✅
- `shop_service.py` + `/api/shop/*` w `backend/app/api/shop.py` ✅ (`SELL_RATIO = 0.5`)
- Zakup odrzuca `value_gp <= 0` (`price_or_catalog_missing`) ✅

---

## Ten dokument (REV 3) — uzupełnienie `value_gp` + widoczność w sklepie

**Cel:** przedmioty fabularne mogą mieć `value_gp = 0` (nie do sprzedaży); broń i reszta katalogu powinny mieć sensowne ceny; UI sklepu nie pokazuje pozycji z ceną 0.

### Zrobione w repo

| Element | Stan |
|--------|------|
| Migracja `ADMIN_MIGRATIONS` | Dodany `UPDATE game_config_weapons … CASE …` dla broni, które w DB miały `value_gp = 0` (18 kluczy, m.in. `dagger`, `longsword`, `greataxe`, przedmioty magiczne). Uruchamia się przy starcie migracji admin. |
| `get_shop_inventory()` | Pomija pozycje z `value_gp == 0` (np. quest item w `shop_inventory_json` przez pomyłkę). |
| Test | `test_phase9a_shop.py` — `quest_trinket` z ceną 0 w ofercie NPC nie pojawia się na liście. |
| `game_config_items` z `value_gp = 0` | Celowo pozostawione (np. `ancient_map`, `sealed_letter`) — **brak** masowego UPDATE; filtr sklepu je ukrywa. |

### Audyt lokalny (DEV, snapshot)

- `game_config_items`: 40 wierszy, 6 × `value_gp = 0` (fabularne — OK przy filtrze).
- `game_config_weapons`: przed migracją wiele broni miało `0 GP` — migracja REV 3 uzupełnia wyłącznie wymienione klucze przy `value_gp = 0`.

### Weryfikacja po wdrożeniu

```bash
docker compose -f docker-compose.dev.yml exec -T backend python3 -c "from app.migrations_admin import run_admin_migrations; run_admin_migrations()"

docker compose -f docker-compose.dev.yml exec -T backend python3 -m pytest tests/test_phase9a_shop.py -q

curl -sf http://localhost:8100/api/healthz && echo " OK"
```

---

## Oryginalny plan implementacji (referencja — większość już w 9A)

Szczegóły API (`ShopBuyRequest` z `item_type` / `item_key`), testy kupna/sprzedaży i UI modala sklepu są zaimplementowane w kodzie Phase 9A; ten plik domyka **8F-1** pod kątem **cen katalogu** i **oferty sklepu**.

---

## Checklist testów (dokument źródłowy)

| Test | Stan w `test_phase9a_shop.py` |
|------|-------------------------------|
| buy odejmuje gold | `test_buy_item_deducts_gold_and_adds_inventory` ✅ |
| brak gold → 402 | pokryte przez `shop.py` + serwis (integracyjnie można dopisać) |
| sprzedaż ~50% | `test_sell_item_removes_one_and_adds_half_price_gold` ✅ |
| zakup dodaje do ekwipunku | ten sam test buy ✅ |
| sprzedaż usuwa z ekwipunku | `test_sell_item_...` ✅ |
| brak pozycji z ceną 0 w ofercie | `test_shop_inventory_by_key_returns_items_and_gold` (asercja `quest_trinket`) ✅ |

---

## Odpowiedzi Cursora (REV 1) — skrót

1. **Branch:** `phase-8f-1-economy-gold-flow`
2. **`value_gp = 0` w items:** 6 rekordów fabularnych — zostają; sklep filtruje.
3. **Migracje:** `migrations_admin.py` (`ADMIN_MIGRATIONS` + `ADMIN_SEEDS`)
4. **Sklep:** `SELL_RATIO = 0.5` w `shop_service.py`

---

## Notatki po implementacji *(Perplexity — opcjonalnie)*

*(Do uzupełnienia po review.)*
