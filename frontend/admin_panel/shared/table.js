import { openModal } from "/admin_panel/shared/modal.js?v=17";

/**
 * @param {string} message
 * @param {{ dangerous?: boolean, showForceCheckbox?: boolean, forceCheckboxLabel?: string }} [options]
 */
export function showConfirm(message, options = {}) {
  const dangerous = !!options.dangerous;
  const showForce = !!options.showForceCheckbox;
  const forceCheckboxLabel = options.forceCheckboxLabel ?? "Force update (row is locked)";

  return new Promise((resolve) => {
    const wrap = document.createElement("div");
    const p = document.createElement("p");
    p.className = "modal-message";
    p.textContent = message;
    wrap.appendChild(p);

    let forceInput = null;
    if (showForce) {
      const row = document.createElement("label");
      row.className = "modal-checkbox-row";
      forceInput = document.createElement("input");
      forceInput.type = "checkbox";
      const span = document.createElement("span");
      span.textContent = forceCheckboxLabel;
      row.appendChild(forceInput);
      row.appendChild(span);
      wrap.appendChild(row);
    }

    const { close } = openModal({
      title: dangerous ? "Confirm" : "Please confirm",
      content: wrap,
      footer: [
        {
          label: "Cancel",
          class: "secondary-btn",
          onClick: () => {
            close();
            resolve(showForce ? { ok: false, force: false } : false);
          },
        },
        {
          label: "OK",
          class: dangerous ? "primary-btn danger-btn" : "primary-btn",
          onClick: () => {
            if (showForce && forceInput && !forceInput.checked) {
              return;
            }
            close();
            resolve(showForce ? { ok: true, force: !!forceInput?.checked } : true);
          },
        },
      ],
    });
  });
}

function cellDisplayValue(row, col) {
  const raw = row[col.key];
  if (col.type === "boolean") {
    return raw === true || raw === 1 || raw === "1";
  }
  if (col.type === "locked") {
    return raw ? "🔒" : "";
  }
  if (raw === null || raw === undefined) {
    return "";
  }
  return String(raw);
}

function isRowLocked(row) {
  return !!(row.locked_at && String(row.locked_at).trim());
}

/**
 * @param {object} row
 * @param {{ key: string, type?: string, sortValue?: (row: object) => unknown, sortable?: boolean }} col
 */
function getSortValueForColumn(row, col) {
  if (typeof col.sortValue === "function") {
    return col.sortValue(row);
  }
  const raw = row[col.key];
  if (col.type === "boolean") {
    return cellDisplayValue(row, col) ? 1 : 0;
  }
  if (col.type === "checkbox-set" && Array.isArray(raw)) {
    return raw.join(",");
  }
  if (Array.isArray(raw)) {
    return raw.join(",");
  }
  if (raw == null) {
    return null;
  }
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return raw;
  }
  if (col.type === "number") {
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }
  if (typeof raw === "object") {
    return JSON.stringify(raw);
  }
  return String(raw);
}

/** @param {unknown} va @param {unknown} vb */
function compareSortValues(va, vb) {
  if (va === vb) {
    return 0;
  }
  const aEmpty = va == null || (typeof va === "string" && va === "");
  const bEmpty = vb == null || (typeof vb === "string" && vb === "");
  if (aEmpty && bEmpty) {
    return 0;
  }
  if (aEmpty) {
    return 1;
  }
  if (bEmpty) {
    return -1;
  }
  if (typeof va === "number" && typeof vb === "number") {
    return va < vb ? -1 : 1;
  }
  return String(va).localeCompare(String(vb), undefined, { numeric: true, sensitivity: "base" });
}

/**
 * @param {Array<object>} rows
 * @param {object} col
 * @param {"asc" | "desc"} dir
 */
function sortRowsCopy(rows, col, dir) {
  const mult = dir === "asc" ? 1 : -1;
  const indexed = rows.map((r, i) => ({ r, i }));
  indexed.sort((a, b) => {
    const va = getSortValueForColumn(a.r, col);
    const vb = getSortValueForColumn(b.r, col);
    const c = compareSortValues(va, vb);
    if (c !== 0) {
      return mult * c;
    }
    return a.i - b.i;
  });
  return indexed.map((x) => x.r);
}

/** @param {string | { value: string, label?: string }} opt */
function _selectOptValue(opt) {
  if (typeof opt === "string") {
    return opt;
  }
  return String(opt.value ?? "");
}

/** @param {string | { value: string, label?: string }} opt */
function _selectOptLabel(opt) {
  if (typeof opt === "string") {
    return opt;
  }
  return String(opt.label ?? opt.value ?? "");
}

/**
 * @param {object} row
 * @param {{ key: string, editOptions?: Array<string | { value: string, label?: string }> }} col
 */
function _selectDropdownLabel(row, col) {
  const v = row[col.key];
  const opts = col.editOptions || [];
  const s = v == null ? "" : String(v);
  for (let i = 0; i < opts.length; i += 1) {
    if (_selectOptValue(opts[i]) === s) {
      return _selectOptLabel(opts[i]);
    }
  }
  return s || "—";
}

/**
 * @param {HTMLElement} container
 * @param {Array<{ key: string, label: string, editable?: boolean, type?: string }>} columns
 * @param {Array<object>|null} rows null = loading skeleton
 * @param {{
 *   onEdit?: (row: object, key: string, newValue: unknown, meta?: { force?: boolean }) => Promise<void>,
 *   onDelete?: (row: object, meta?: { force?: boolean }) => Promise<void>,
 *   extraActions?: (row: object) => Array<{ label: string, class?: string, onClick: () => void | Promise<void> }>,
 *   sortable?: boolean,
 * }} [options]
 */
export function renderTable(container, columns, rows, options = {}) {
  const onEdit = options.onEdit;
  const onDelete = options.onDelete;
  const extraActions = options.extraActions;
  const sortableTable = options.sortable !== false;

  if (!container.__adminSort) {
    container.__adminSort = { key: null, dir: "asc" };
  }
  const sortState = container.__adminSort;
  if (sortState.key && !columns.some((c) => c.key === sortState.key)) {
    sortState.key = null;
    sortState.dir = "asc";
  }

  let displayRows = rows;
  if (sortableTable && Array.isArray(rows) && rows.length && sortState.key) {
    const col = columns.find((c) => c.key === sortState.key && c.sortable !== false);
    if (col) {
      displayRows = sortRowsCopy(rows, col, sortState.dir === "desc" ? "desc" : "asc");
    }
  }

  container.innerHTML = "";
  const wrap = document.createElement("div");
  wrap.className = "admin-table-wrap";

  const table = document.createElement("table");
  table.className = "admin-table";

  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  columns.forEach((c) => {
    const th = document.createElement("th");
    const canSort = sortableTable && c.sortable !== false && Array.isArray(rows);
    if (!canSort) {
      th.textContent = c.label;
    } else {
      th.className = "admin-table-th-sortable";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "admin-table-sort-btn";
      btn.setAttribute("aria-label", `Sort by ${c.label}`);
      const lab = document.createElement("span");
      lab.className = "admin-table-sort-label";
      lab.textContent = c.label;
      btn.appendChild(lab);
      const ind = document.createElement("span");
      ind.className = "admin-table-sort-indicator";
      ind.setAttribute("aria-hidden", "true");
      if (sortState.key === c.key) {
        ind.textContent = sortState.dir === "asc" ? "▲" : "▼";
        th.setAttribute("aria-sort", sortState.dir === "asc" ? "ascending" : "descending");
      } else {
        ind.textContent = "⇅";
        ind.classList.add("admin-table-sort-inactive");
      }
      btn.appendChild(ind);
      btn.addEventListener("click", () => {
        if (sortState.key === c.key) {
          sortState.dir = sortState.dir === "asc" ? "desc" : "asc";
        } else {
          sortState.key = c.key;
          sortState.dir = "asc";
        }
        renderTable(container, columns, rows, options);
      });
      th.appendChild(btn);
    }
    hr.appendChild(th);
  });
  if (onDelete || extraActions) {
    const th = document.createElement("th");
    th.className = "admin-table-actions-col";
    th.textContent = "";
    hr.appendChild(th);
  }
  thead.appendChild(hr);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  const actionCols = onDelete || extraActions ? 1 : 0;

  if (rows === null) {
    for (let i = 0; i < 3; i += 1) {
      const tr = document.createElement("tr");
      tr.className = "admin-table-skeleton-row";
      const td = document.createElement("td");
      td.colSpan = columns.length + actionCols;
      const bar = document.createElement("div");
      bar.className = "admin-table-skeleton-bar";
      td.appendChild(bar);
      tr.appendChild(td);
      tbody.appendChild(tr);
    }
  } else if (!rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = columns.length + actionCols;
    td.className = "admin-table-empty";
    td.textContent = "No rows yet.";
    tr.appendChild(td);
    tbody.appendChild(tr);
  } else {
    displayRows.forEach((row) => {
      const locked = isRowLocked(row);
      const tr = document.createElement("tr");
      if (locked) {
        tr.classList.add("admin-table-row-locked");
      }

      columns.forEach((col, colIdx) => {
        const td = document.createElement("td");
        td.dataset.col = col.key;

        if (col.editable && onEdit && col.type === "badge" && col.editType === "select" && Array.isArray(col.editOptions)) {
          const display = document.createElement("div");
          display.className = "admin-table-cell-edit-host";
          const pill = document.createElement("span");
          let cls = "admin-badge";
          if (col.badgeClass) {
            const extra = typeof col.badgeClass === "function" ? col.badgeClass(row) : col.badgeClass;
            if (extra) {
              cls += ` ${extra}`;
            }
          }
          pill.className = cls;
          pill.textContent = String(row[col.key] ?? "");
          display.appendChild(pill);

          const applyBadge = () => {
            pill.textContent = String(row[col.key] ?? "");
            let c = "admin-badge";
            if (col.badgeClass) {
              const ex = typeof col.badgeClass === "function" ? col.badgeClass(row) : col.badgeClass;
              if (ex) {
                c += ` ${ex}`;
              }
            }
            pill.className = c;
          };

          pill.addEventListener("click", () => {
            if (display.querySelector("select")) {
              return;
            }
            const sel = document.createElement("select");
            sel.className = "admin-table-cell-input admin-table-cell-select";
            col.editOptions.forEach((opt) => {
              const o = document.createElement("option");
              o.value = String(opt);
              o.textContent = String(opt);
              sel.appendChild(o);
            });
            const cur = String(row[col.key] ?? "");
            sel.value = col.editOptions.includes(cur) ? cur : col.editOptions[0];

            let committed = false;
            const restorePill = () => {
              if (sel.parentNode) {
                sel.replaceWith(pill);
              }
              applyBadge();
            };

            const runCommit = async () => {
              if (committed) {
                return;
              }
              committed = true;
              const newVal = sel.value;
              let force = false;
              if (locked) {
                const res = await showConfirm(
                  "This row is locked. Check “Force update” to save your edit.",
                  { showForceCheckbox: true },
                );
                if (!res || !res.ok) {
                  committed = false;
                  restorePill();
                  return;
                }
                force = !!res.force;
              }
              try {
                await onEdit(row, col.key, newVal, { force });
                row[col.key] = newVal;
                restorePill();
              } catch (_err) {
                committed = false;
                restorePill();
              }
            };

            pill.replaceWith(sel);
            sel.focus();

            sel.addEventListener("change", () => {
              void runCommit();
            });
            sel.addEventListener("blur", () => {
              setTimeout(() => {
                if (!committed && display.contains(sel)) {
                  void runCommit();
                }
              }, 0);
            });
            sel.addEventListener("keydown", (ev) => {
              if (ev.key === "Escape") {
                ev.preventDefault();
                committed = true;
                restorePill();
              }
            });
          });

          td.appendChild(display);
        } else if (
          col.type === "select-dropdown" &&
          col.editable &&
          onEdit &&
          Array.isArray(col.editOptions)
        ) {
          const display = document.createElement("div");
          display.className = "admin-table-cell-edit-host";
          const span = document.createElement("span");
          span.className = "admin-table-cell-text";
          const prefix = colIdx === 0 && locked ? "🔒 " : "";
          span.textContent = prefix + _selectDropdownLabel(row, col);
          display.appendChild(span);
          span.addEventListener("click", () => {
            if (display.querySelector("select")) {
              return;
            }
            const sel = document.createElement("select");
            sel.className = "admin-table-cell-input admin-table-cell-select";
            col.editOptions.forEach((opt) => {
              const o = document.createElement("option");
              o.value = _selectOptValue(opt);
              o.textContent = _selectOptLabel(opt);
              sel.appendChild(o);
            });
            const cur = row[col.key] == null ? "" : String(row[col.key]);
            sel.value = col.editOptions.some((o) => _selectOptValue(o) === cur) ? cur : _selectOptValue(col.editOptions[0]);

            let committed = false;
            const restore = () => {
              if (sel.parentNode) {
                sel.replaceWith(span);
              }
              span.textContent = prefix + _selectDropdownLabel(row, col);
            };

            const runCommit = async () => {
              if (committed) {
                return;
              }
              committed = true;
              const newVal = sel.value;
              let force = false;
              if (locked) {
                const res = await showConfirm(
                  "This row is locked. Check “Force update” to save your edit.",
                  { showForceCheckbox: true },
                );
                if (!res || !res.ok) {
                  committed = false;
                  restore();
                  return;
                }
                force = !!res.force;
              }
              try {
                await onEdit(row, col.key, newVal, { force });
                row[col.key] = newVal;
                restore();
              } catch (_err) {
                committed = false;
                restore();
              }
            };

            span.replaceWith(sel);
            sel.focus();

            sel.addEventListener("change", () => {
              void runCommit();
            });
            sel.addEventListener("blur", () => {
              setTimeout(() => {
                if (!committed && display.contains(sel)) {
                  void runCommit();
                }
              }, 0);
            });
            sel.addEventListener("keydown", (ev) => {
              if (ev.key === "Escape") {
                ev.preventDefault();
                committed = true;
                restore();
              }
            });
          });
          td.appendChild(display);
        } else if (col.type === "boolean" && col.editable !== false && onEdit) {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "toggle-btn";
          const syncBtn = () => {
            btn.textContent = cellDisplayValue(row, col) ? "✅" : "❌";
          };
          syncBtn();
          btn.addEventListener("click", async () => {
            const next = !cellDisplayValue(row, col);
            let force = false;
            if (locked) {
              const res = await showConfirm(
                "This row is locked. Check “Force update” to apply the toggle.",
                { showForceCheckbox: true },
              );
              if (!res || !res.ok) {
                return;
              }
              force = !!res.force;
            }
            try {
              await onEdit(row, col.key, next, { force });
              syncBtn();
              Object.assign(row, { [col.key]: next });
            } catch (_e) {
              syncBtn();
              /* caller surfaces toast */
            }
          });
          td.appendChild(btn);
        } else if (col.type === "checkbox-set" && col.editable && onEdit && Array.isArray(col.editOptions)) {
          const display = document.createElement("div");
          display.className = "admin-table-cell-edit-host";
          const span = document.createElement("span");
          span.className = "admin-table-cell-text";
          const prefix = colIdx === 0 && locked ? "🔒 " : "";
          const textForRow = () =>
            typeof col.formatDisplay === "function"
              ? String(col.formatDisplay(row))
              : (Array.isArray(row[col.key]) ? row[col.key].join(", ") : "");
          span.textContent = prefix + textForRow();
          span.addEventListener("click", () => {
            if (display.querySelector(".admin-checkbox-set-editor")) {
              return;
            }
            const editor = document.createElement("div");
            editor.className = "admin-checkbox-set-editor";
            const current = Array.isArray(row[col.key]) ? row[col.key].map((c) => String(c).toLowerCase()) : [];
            const selected = new Set(current);
            col.editOptions.forEach((opt) => {
              const lab = document.createElement("label");
              lab.className = "modal-checkbox-row";
              const cb = document.createElement("input");
              cb.type = "checkbox";
              cb.value = String(opt);
              cb.checked = selected.has(String(opt).toLowerCase());
              lab.appendChild(cb);
              lab.appendChild(document.createTextNode(String(opt)));
              editor.appendChild(lab);
            });
            const okBtn = document.createElement("button");
            okBtn.type = "button";
            okBtn.className = "primary-btn";
            okBtn.textContent = "OK";
            editor.appendChild(okBtn);
            span.replaceWith(editor);

            const restore = () => {
              if (editor.parentNode) {
                editor.replaceWith(span);
              }
              span.textContent = prefix + textForRow();
            };

            const runCommit = async () => {
              const next = [];
              editor.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
                if (cb.checked) {
                  next.push(String(cb.value).toLowerCase());
                }
              });
              let force = false;
              if (locked) {
                const res = await showConfirm(
                  "This row is locked. Check “Force update” to save your edit.",
                  { showForceCheckbox: true },
                );
                if (!res || !res.ok) {
                  restore();
                  return;
                }
                force = !!res.force;
              }
              try {
                await onEdit(row, col.key, next, { force });
                row[col.key] = next;
                restore();
              } catch (_err) {
                restore();
              }
            };

            okBtn.addEventListener("click", () => {
              void runCommit();
            });
            editor.addEventListener("keydown", (ev) => {
              if (ev.key === "Escape") {
                ev.preventDefault();
                restore();
              }
            });
          });
          display.appendChild(span);
          td.appendChild(display);
        } else if (col.editable && onEdit && col.type !== "locked") {
          const display = document.createElement("div");
          display.className = "admin-table-cell-edit-host";
          const prefix = colIdx === 0 && locked ? "🔒 " : "";
          const textVal =
            col.type === "number" ? String(Number(row[col.key] ?? 0)) : String(row[col.key] ?? "");
          const shown = typeof col.formatDisplay === "function" ? String(col.formatDisplay(row)) : textVal;
          display.innerHTML = `<span class="admin-table-cell-text">${prefix}${shown}</span>`;

          const span = display.querySelector(".admin-table-cell-text");
          if (col.tooltipField) {
            const tip = row[col.tooltipField];
            if (tip != null && String(tip).trim()) {
              span.title = String(tip);
            }
          }
          span.addEventListener("click", () => {
            if (display.querySelector("input,textarea")) {
              return;
            }
            const startVal =
              col.type === "number" ? Number(row[col.key] ?? 0) : String(row[col.key] ?? "");
            const editor =
              col.type === "textarea"
                ? document.createElement("textarea")
                : document.createElement("input");
            editor.className = "admin-table-cell-input";
            if (col.type === "number") {
              editor.type = "number";
              editor.value = String(Number.isFinite(startVal) ? startVal : 0);
              if (col.min != null) {
                editor.min = String(col.min);
              }
              if (col.max != null) {
                editor.max = String(col.max);
              }
            } else if (col.type === "textarea") {
              editor.rows = 4;
              editor.value = String(startVal);
            } else {
              editor.type = "text";
              editor.value = String(startVal);
            }

            let committed = false;

            const cancel = () => {
              const revert =
                typeof col.formatDisplay === "function"
                  ? String(col.formatDisplay(row))
                  : String(row[col.key] ?? "");
              span.textContent = prefix + revert;
              editor.remove();
              display.classList.remove("is-editing");
            };

            const runCommit = async () => {
              if (committed) {
                return;
              }
              committed = true;
              let newVal;
              if (col.type === "number") {
                newVal = Number(editor.value);
                if (!Number.isFinite(newVal)) {
                  newVal = 0;
                }
              } else {
                newVal = editor.value;
              }
              let force = false;
              if (locked) {
                const res = await showConfirm(
                  "This row is locked. Check “Force update” to save your edit.",
                  { showForceCheckbox: true },
                );
                if (!res || !res.ok) {
                  committed = false;
                  cancel();
                  return;
                }
                force = !!res.force;
              }
              try {
                await onEdit(row, col.key, newVal, { force });
                row[col.key] = newVal;
                span.textContent =
                  prefix +
                  (typeof col.formatDisplay === "function" ? String(col.formatDisplay(row)) : String(newVal));
              } catch (_err) {
                committed = false;
                cancel();
                return;
              }
              editor.remove();
              display.classList.remove("is-editing");
            };

            span.textContent = "";
            span.appendChild(editor);
            display.classList.add("is-editing");
            editor.focus();
            if (editor.select) {
              editor.select();
            }

            editor.addEventListener("keydown", (ev) => {
              if (col.type !== "textarea" && ev.key === "Enter") {
                ev.preventDefault();
                void runCommit();
              } else if (ev.key === "Escape") {
                ev.preventDefault();
                committed = true;
                cancel();
              }
            });
            editor.addEventListener("blur", () => {
              setTimeout(() => {
                if (!committed) {
                  void runCommit();
                }
              }, 0);
            });
          });

          td.appendChild(display);
          } else {
            td.classList.add("admin-table-cell-readonly");
            const prefix = colIdx === 0 && locked ? "🔒 " : "";
            if (col.tooltipField) {
              const tip = row[col.tooltipField];
              if (tip != null && String(tip).trim()) {
                td.title = String(tip);
              }
            }
            if (typeof col.formatDisplay === "function") {
              td.textContent = prefix + col.formatDisplay(row);
            } else if (col.type === "badge") {
            const pill = document.createElement("span");
            let cls = "admin-badge";
            if (col.badgeClass) {
              const extra = typeof col.badgeClass === "function" ? col.badgeClass(row) : col.badgeClass;
              if (extra) {
                cls += ` ${extra}`;
              }
            }
            pill.className = cls;
            pill.textContent = String(row[col.key] ?? "");
            td.appendChild(pill);
          } else if (col.type === "boolean") {
            td.textContent = cellDisplayValue(row, col) ? "✅" : "❌";
          } else {
            td.textContent = prefix + cellDisplayValue(row, col);
          }
        }
        tr.appendChild(td);
      });

      if (onDelete || extraActions) {
        const td = document.createElement("td");
        td.className = "admin-table-actions";
        const extras = extraActions ? extraActions(row) : [];
        extras.forEach((ex) => {
          const b = document.createElement("button");
          b.type = "button";
          b.textContent = ex.label;
          if (ex.class) {
            b.className = ex.class;
          }
          b.addEventListener("click", () => {
            void ex.onClick();
          });
          td.appendChild(b);
        });
        if (onDelete) {
          const del = document.createElement("button");
          del.type = "button";
          del.className = "secondary-btn danger-outline";
          del.textContent = "Delete";
          del.addEventListener("click", async () => {
            let force = false;
            if (locked) {
              const res = await showConfirm(
                "This row is locked. Check Force delete to remove it anyway.",
                {
                  dangerous: true,
                  showForceCheckbox: true,
                  forceCheckboxLabel: "Force delete (row is locked)",
                },
              );
              if (!res || !res.ok) {
                return;
              }
              force = !!res.force;
            } else {
              const ok = await showConfirm("Delete this row?", { dangerous: true });
              if (!ok) {
                return;
              }
            }
            await onDelete(row, { force });
          });
          td.appendChild(del);
        }
        tr.appendChild(td);
      }

      tbody.appendChild(tr);
    });
  }

  table.appendChild(tbody);
  wrap.appendChild(table);
  container.appendChild(wrap);
}
