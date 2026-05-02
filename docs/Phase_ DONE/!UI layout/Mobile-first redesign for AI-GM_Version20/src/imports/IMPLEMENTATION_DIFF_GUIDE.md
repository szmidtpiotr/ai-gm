# IMPLEMENTATION_DIFF_GUIDE

## Step 1 - Safety Baseline

- Zrob snapshot UI (mobile + desktop).
- Zweryfikuj kontrakty z `DOM_CONTRACT.md`.
- Zweryfikuj API z `API_INTEGRATION_ASSUMPTIONS.md`.

## Step 2 - Token Layer

- Najpierw podmien tokeny w `styles.css`.
- Nie dotykaj logiki JS.
- Sprawdz kontrast i stany disabled/error.

## Step 3 - Layout Layer

- Dostosuj uklad shella, chatu, composer i sheet panelu.
- W mobile: priorytet na composer + keyboard i bottom-sheet.

## Step 4 - Component Layer

- Dopasuj modale, buttony, inputy, listy.
- Potem elementy dynamiczne: thinking/streaming/roll/combat/slash.

## Step 5 - Regression Checklist

- Login/logout
- Create campaign + create character
- Send turn (SSE)
- Archive toggle
- History summary modal
- Combat start/attack/flee
- Death screen

## Step 6 - Diff Rules

- Preferuj male, czytelne commity:
  - `docs: ...`
  - `style: ...`
  - `ui: ...`
- Kazda zmiana ID/endpointu wymaga osobnego commita z uzasadnieniem.

## Deployment Note

Przy zmianach tylko w dokumentacji Docker restart/rebuild **nie jest potrzebny**.
Przy zmianach frontend CSS/JS moze byc potrzebny hard refresh cache.
