# admin/sections/

FADM (strangler-fig) — po jednym pliku `<key>.js` na sekcję, portowanym z monolitu
`frontend/admin_panel_v3/index.html`.

Każdy plik eksportuje:

```js
export async function init(panel) { /* render sekcji do `panel`, wywołania przez ../shared/api.js */ }
```

Sekcja nieportowana → router pokazuje placeholder „w trakcie migracji → /admin3/#key".
Po porcie + akceptacji: kopia sekcji znika z monolitu admin3 w tym samym commicie (anty-grób).

Kolejność: P1 overview → P2 mechanics → P3 content → P4 world → P6 campaigns → P5 map →
P7 dungeons → P8 forge → P9 players → P10 tools → P11 system → P12 misc.
