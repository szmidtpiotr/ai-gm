import { openModal } from "/admin_panel/shared/modal.js?v=17";

/**
 * @param {string} message
 * @param {{ dangerous?: boolean, showForceCheckbox?: boolean }} [options]
 */
export function showConfirm(message, options = {}) {
  const dangerous = !!options.dangerous;
  const showForce = !!options.showForceCheckbox;

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
      span.textContent = "Force update (row is locked)";
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
 *   onDelete?: (row: object) => Promise<void>,
 *   extraActions?: (row: object) => Array<{ label: string, class?: string, onClick: () => void | Promise<void> }>,
 * }} [options]
 */
export function renderTable(container, columns, rows, options = {}) {
  const onEdit = options.onEdit;
  const onDelete = options.onDelete;
  const extraActions = options.extraActions;

  container.innerHTML = "";
  const wrap = document.createElement("div");
  wrap.className = "admin-table-wrap";

  const table = document.createElement("table");
  table.className = "admin-table";

  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  columns.forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c.label;
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
    rows.forEach((row) => {
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
          const onVal = cellDisplayValue(row, col);
          btn.textContent = onVal ? "✅" : "❌";
          btn.addEventListener("click", async () => {
            const next = !onVal;
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
              btn.textContent = next ? "✅" : "❌";
              Object.assign(row, { [col.key]: next ? 1 : 0 });
            } catch (_e) {
              /* caller surfaces toast */
            }
          });
          td.appendChild(btn);
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
            const ok = await showConfirm("Delete this row?", { dangerous: true });
            if (!ok) {
              return;
            }
            await onDelete(row);
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
