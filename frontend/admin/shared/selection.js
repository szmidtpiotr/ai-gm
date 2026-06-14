// #588 — współdzielone helpery zaznaczania wierszy tabeli (multi-select).
// Wydzielone z players.js, by każda sekcja z paskiem zaznaczenia (players, campaigns…)
// mogła ich użyć bez duplikacji. Parametryzowane prefixem: `${prefix}-row-check`,
// `${prefix}-sel-bar`, `${prefix}-sel-count`.

export function toggleAll(prefix, master) {
  document.querySelectorAll(`.${prefix}-row-check`).forEach(cb => {
    cb.checked = master.checked;
    cb.closest('tr')?.classList.toggle('selected', master.checked);
  });
  rowCheck(prefix);
}

export function rowCheck(prefix) {
  const checked = document.querySelectorAll(`.${prefix}-row-check:checked`).length;
  const bar   = document.getElementById(`${prefix}-sel-bar`);
  const count = document.getElementById(`${prefix}-sel-count`);
  if (bar)   bar.classList.toggle('visible', checked > 0);
  if (count) count.textContent = `${checked} zaznaczonych`;
  document.querySelectorAll(`.${prefix}-row-check`).forEach(cb => {
    cb.closest('tr')?.classList.toggle('selected', cb.checked);
  });
}
