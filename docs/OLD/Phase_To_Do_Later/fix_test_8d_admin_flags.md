# ToDo: Napraw faile w `test_8d_admin_flags.py`

> **Priorytet:** średni (nie blokuje aktualnych zadań, ale zaciemnia obraz regresji)
> **Odkryte przy:** 9A-0b `Grant Gold` regresja, 2026-04-29
> **Branch:** `phase-8d-location-integrity`

---

## Problem

Podczas pełnego przebiegu `pytest tests/ -q` widać faile w:

```
tests/test_8d_admin_flags.py ...FFF...
```

Nie są nowym problemem wprowadzonym przez `Grant Gold` — istniały wcześniej. Jednak dopiero podczas regresji po 9A-0b stały się widoczne.

---

## Co zrobić

1. Uruchom testy izolowane i przejrzyj błędy:
   ```bash
   docker compose -f docker-compose.dev.yml exec -T backend python3 -m pytest \
     tests/test_8d_admin_flags.py -v
   ```
2. Zidentyfikuj czy fail pochodzi z:
   - brakującej migracji / kolumny w DB,
   - zmiany API endpointów admina (np. Phase 8D LOC-4 zmieniła admin router),
   - błędnego fixture lub hardcoded danych testowych.
3. Naprawić lub usunąć/zaktualizować testy jeśli testują funkcjonalność która już nie istnieje w tej formie.

---

## Dlaczego ważne

Dopóki `test_8d_admin_flags.py` failuje, `pytest tests/ -q` nie daje wiarygodnego obrazu regresji. Każde nowe zadanie raportuje "są faile" ale trudno ocenić czy to nowe czy stare.

---

## Nie blokuje

Aktualne funkcjonalności działają. Faile są w testach, nie w kodzie produkcyjnym.
