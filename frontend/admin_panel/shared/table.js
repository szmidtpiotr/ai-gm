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

function badgeCellText(row, col) {
  if (typeof col.badgeText === "function") {
    return String(col.badgeText(row));
  }
  return String(row[col.key] ?? "");
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

const FILTER_ALL = "__admin_filter_all__";
const FILTER_EMPTY = "__admin_filter_empty__";

function isColumnFilterable(col) {
  if (!col || col.filterable === false) {
    return false;
  }
  if (Array.isArray(col.filterOptions)) {
    return true;
  }
  if (col.type === "boolean") {
    return true;
  }
  if (col.type === "checkbox-set" && Array.isArray(col.editOptions)) {
    return true;
  }
  if (col.type === "select-dropdown" && Array.isArray(col.editOptions)) {
    return true;
  }
  if (col.editType === "select" && Array.isArray(col.editOptions)) {
    return true;
  }
  return false;
}

function normalizeFilterToken(value) {
  if (value == null) {
    return FILTER_EMPTY;
  }
  const s = String(value);
  return s === "" ? FILTER_EMPTY : s;
}

function filterOptionsForColumn(col) {
  let base = [];
  if (Array.isArray(col.filterOptions)) {
    base = col.filterOptions;
  } else if (col.type === "boolean") {
    base = [
      { value: "true", label: "Yes" },
      { value: "false", label: "No" },
    ];
  } else if (Array.isArray(col.editOptions)) {
    base = col.editOptions;
  }

  const out = [];
  const seen = new Set();
  base.forEach((opt) => {
    const rawValue = typeof opt === "string" ? opt : (opt?.value ?? "");
    const value = normalizeFilterToken(rawValue);
    if (seen.has(value)) {
      return;
    }
    seen.add(value);
    const rawLabel = typeof opt === "string" ? opt : (opt?.label ?? rawValue);
    out.push({
      value,
      label: value === FILTER_EMPTY ? (rawLabel || "— empty —") : String(rawLabel),
    });
  });
  return out;
}

function getRowFilterTokens(row, col) {
  if (typeof col.filterValue === "function") {
    const custom = col.filterValue(row);
    if (Array.isArray(custom)) {
      return custom.map((v) => normalizeFilterToken(v));
    }
    return [normalizeFilterToken(custom)];
  }
  const raw = row[col.key];
  if (col.type === "boolean") {
    return [raw === true || raw === 1 || raw === "1" ? "true" : "false"];
  }
  if (Array.isArray(raw)) {
    return raw.map((v) => normalizeFilterToken(v));
  }
  return [normalizeFilterToken(raw)];
}

function rowMatchesFilters(row, filterableColumns, filterState) {
  for (let i = 0; i < filterableColumns.length; i += 1) {
    const col = filterableColumns[i];
    const selected = filterState[col.key] || FILTER_ALL;
    if (selected === FILTER_ALL) {
      continue;
    }
    const tokens = getRowFilterTokens(row, col);
    if (!tokens.includes(selected)) {
      return false;
    }
  }
  return true;
}

/**
 * Case-insensitive match across visible columns and any extra keys on the row (JSON cells, etc.).
 * @param {object} row
 * @param {Array<{ key: string }>} columns
 * @param {string} q normalized lowercase query
 */
function rowMatchesTextSearch(row, columns, q) {
  if (!q) {
    return true;
  }
  const parts = [];
  columns.forEach((c) => {
    parts.push(String(getSortValueForColumn(row, c) ?? ""));
  });
  Object.keys(row).forEach((k) => {
    if (!columns.some((c) => c.key === k)) {
      const v = row[k];
      if (v != null && typeof v === "object") {
        try {
          parts.push(JSON.stringify(v));
        } catch (_e) {
          parts.push(String(v));
        }
      } else {
        parts.push(String(v ?? ""));
      }
    }
  });
  return parts.join("\u0000").toLowerCase().includes(q);
}

function defaultRowId(row, options = {}) {
  if (typeof options.getRowId === "function") {
    return String(options.getRowId(row));
  }
  if (typeof options.rowKey === "string" && row?.[options.rowKey] != null) {
    return String(row[options.rowKey]);
  }
  if (row?.key != null) {
    return String(row.key);
  }
  if (row?.id != null) {
    return String(row.id);
  }
  return JSON.stringify(row);
}

function normalizeExportRows(rows, options = {}) {
  if (typeof options.exportRows === "function") {
    return options.exportRows(rows);
  }
  if (typeof options.exportRow === "function") {
    return rows.map((row) => options.exportRow(row));
  }
  return rows;
}

function downloadTableJson(rows, options = {}) {
  const payload = normalizeExportRows(rows, options);
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  const filenameBase = String(options.exportFilename || options.tableName || "admin_table")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "");
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  a.download = `${filenameBase || "admin_table"}_${y}${m}${day}.json`;
  a.click();
  URL.revokeObjectURL(blobUrl);
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
 *   selectable?: boolean,
 *   rowKey?: string,
 *   getRowId?: (row: object) => string,
 *   tableName?: string,
 *   exportFilename?: string,
 *   exportRows?: (rows: Array<object>) => unknown,
 *   exportRow?: (row: object) => unknown,
 *   showTextSearch?: boolean,
 *   searchPlaceholder?: string,
 * }} [options]
 */
export function renderTable(container, columns, rows, options = {}) {
  const onEdit = options.onEdit;
  const onDelete = options.onDelete;
  const extraActions = options.extraActions;
  const sortableTable = options.sortable !== false;
  const selectable = !!options.selectable;

  if (!container.__adminSort) {
    container.__adminSort = { key: null, dir: "asc" };
  }
  const sortState = container.__adminSort;
  if (sortState.key && !columns.some((c) => c.key === sortState.key)) {
    sortState.key = null;
    sortState.dir = "asc";
  }

  if (!container.__adminFilters) {
    container.__adminFilters = {};
  }
  const filterState = container.__adminFilters;
  const filterableColumns = columns.filter((c) => isColumnFilterable(c));
  Object.keys(filterState).forEach((key) => {
    if (!filterableColumns.some((c) => c.key === key)) {
      delete filterState[key];
    }
  });

  let displayRows = rows;
  if (Array.isArray(rows) && filterableColumns.length) {
    displayRows = rows.filter((row) => rowMatchesFilters(row, filterableColumns, filterState));
  }

  const textSearchOn = options.showTextSearch === true;
  if (typeof container.__adminTextSearch !== "string") {
    container.__adminTextSearch = "";
  }
  const textQ = (container.__adminTextSearch || "").trim().toLowerCase();
  if (textSearchOn && textQ && Array.isArray(displayRows)) {
    displayRows = displayRows.filter((row) => rowMatchesTextSearch(row, columns, textQ));
  }

  if (sortableTable && Array.isArray(displayRows) && displayRows.length && sortState.key) {
    const col = columns.find((c) => c.key === sortState.key && c.sortable !== false);
    if (col) {
      displayRows = sortRowsCopy(displayRows, col, sortState.dir === "desc" ? "desc" : "asc");
    }
  }

  container.innerHTML = "";
  const wrap = document.createElement("div");
  wrap.className = "admin-table-wrap";

  if (textSearchOn && Array.isArray(rows)) {
    const searchRow = document.createElement("div");
    searchRow.className = "admin-table-search-row";
    const inp = document.createElement("input");
    inp.type = "search";
    inp.className = "admin-table-search-input";
    inp.placeholder = options.searchPlaceholder || "Search this table…";
    inp.setAttribute("aria-label", "Search rows");
    inp.value = container.__adminTextSearch || "";
    inp.addEventListener("input", (ev) => {
      const t = ev.target;
      container.__adminTextSearch = t.value;
      const len = t.value.length;
      const start = typeof t.selectionStart === "number" ? t.selectionStart : len;
      const end = typeof t.selectionEnd === "number" ? t.selectionEnd : len;
      container.__adminTextSearchCaretPending = { start, end };
      renderTable(container, columns, rows, options);
    });
    searchRow.appendChild(inp);
    wrap.appendChild(searchRow);
  }

  if (!container.__adminSelected) {
    container.__adminSelected = new Set();
  }
  const selectedState = container.__adminSelected;
  if (Array.isArray(rows)) {
    const validIds = new Set(rows.map((row) => defaultRowId(row, options)));
    [...selectedState].forEach((id) => {
      if (!validIds.has(id)) {
        selectedState.delete(id);
      }
    });
  } else {
    selectedState.clear();
  }
  const visibleRowIds = Array.isArray(displayRows) ? displayRows.map((row) => defaultRowId(row, options)) : [];
  const selectedVisibleCount = visibleRowIds.filter((id) => selectedState.has(id)).length;
  const selectedRows = Array.isArray(rows)
    ? rows.filter((row) => selectedState.has(defaultRowId(row, options)))
    : [];

  if (selectable && Array.isArray(rows)) {
    const toolbar = document.createElement("div");
    toolbar.className = "admin-table-toolbar";
    const left = document.createElement("div");
    left.className = "admin-table-toolbar-left";
    left.textContent = `Selected: ${selectedRows.length}`;
    toolbar.appendChild(left);
    const right = document.createElement("div");
    right.className = "admin-table-toolbar-actions";

    const mkBtn = (label, cls, onClick, disabled = false) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = cls;
      btn.textContent = label;
      btn.disabled = !!disabled;
      btn.addEventListener("click", () => {
        void onClick();
      });
      right.appendChild(btn);
      return btn;
    };

    mkBtn("Select visible", "secondary-btn", () => {
      visibleRowIds.forEach((id) => selectedState.add(id));
      renderTable(container, columns, rows, options);
    }, !visibleRowIds.length);

    mkBtn("Clear selection", "secondary-btn", () => {
      selectedState.clear();
      renderTable(container, columns, rows, options);
    }, !selectedRows.length);

    mkBtn("Export all", "secondary-btn", () => {
      downloadTableJson(rows, options);
    }, !rows.length);

    mkBtn("Export selected", "secondary-btn", () => {
      downloadTableJson(selectedRows, options);
    }, !selectedRows.length);

    if (onDelete) {
      mkBtn("Delete selected", "secondary-btn danger-outline", async () => {
        const ok = await showConfirm(
          `Delete ${selectedRows.length} selected row(s)?`,
          { dangerous: true },
        );
        if (!ok) {
          return;
        }
        let success = 0;
        const deletedIds = new Set();
        const failures = [];
        for (let i = 0; i < selectedRows.length; i += 1) {
          const row = selectedRows[i];
          const rowId = defaultRowId(row, options);
          try {
            await onDelete(row, { force: false });
            selectedState.delete(rowId);
            deletedIds.add(rowId);
            success += 1;
          } catch (err) {
            failures.push(rowId);
          }
        }
        if (failures.length) {
          window.alert?.(
            `Deleted ${success} row(s). Failed to delete ${failures.length}: ${failures.join(", ")}`,
          );
        }
        renderTable(container, columns, rows.filter((row) => !deletedIds.has(defaultRowId(row, options))), options);
      }, !selectedRows.length);
    }
    toolbar.appendChild(right);
    wrap.appendChild(toolbar);
  }

  const table = document.createElement("table");
  table.className = "admin-table";

  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  if (selectable && Array.isArray(rows)) {
    const th = document.createElement("th");
    th.className = "admin-table-select-col";
    const allCb = document.createElement("input");
    allCb.type = "checkbox";
    allCb.checked = !!visibleRowIds.length && selectedVisibleCount === visibleRowIds.length;
    allCb.indeterminate = selectedVisibleCount > 0 && selectedVisibleCount < visibleRowIds.length;
    allCb.addEventListener("change", () => {
      if (allCb.checked) {
        visibleRowIds.forEach((id) => selectedState.add(id));
      } else {
        visibleRowIds.forEach((id) => selectedState.delete(id));
      }
      renderTable(container, columns, rows, options);
    });
    th.appendChild(allCb);
    hr.appendChild(th);
  }
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
  if (Array.isArray(rows) && filterableColumns.length) {
    const filterRow = document.createElement("tr");
    filterRow.className = "admin-table-filter-row";
    if (selectable) {
      filterRow.appendChild(document.createElement("th"));
    }
    columns.forEach((c) => {
      const th = document.createElement("th");
      if (isColumnFilterable(c)) {
        const select = document.createElement("select");
        select.className = "admin-table-filter-select";
        const allOpt = document.createElement("option");
        allOpt.value = FILTER_ALL;
        allOpt.textContent = "All";
        select.appendChild(allOpt);
        filterOptionsForColumn(c).forEach((opt) => {
          const o = document.createElement("option");
          o.value = opt.value;
          o.textContent = opt.label;
          select.appendChild(o);
        });
        const current = filterState[c.key] || FILTER_ALL;
        select.value = [...select.options].some((opt) => opt.value === current) ? current : FILTER_ALL;
        if (select.value === FILTER_ALL) {
          delete filterState[c.key];
        }
        select.addEventListener("change", () => {
          if (select.value === FILTER_ALL) {
            delete filterState[c.key];
          } else {
            filterState[c.key] = select.value;
          }
          renderTable(container, columns, rows, options);
        });
        th.appendChild(select);
      }
      filterRow.appendChild(th);
    });
    if (onDelete || extraActions) {
      filterRow.appendChild(document.createElement("th"));
    }
    thead.appendChild(filterRow);
  }
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  const selectionCols = selectable && Array.isArray(rows) ? 1 : 0;
  const actionCols = onDelete || extraActions ? 1 : 0;

  if (rows === null) {
    for (let i = 0; i < 3; i += 1) {
      const tr = document.createElement("tr");
      tr.className = "admin-table-skeleton-row";
      const td = document.createElement("td");
      td.colSpan = columns.length + actionCols + selectionCols;
      const bar = document.createElement("div");
      bar.className = "admin-table-skeleton-bar";
      td.appendChild(bar);
      tr.appendChild(td);
      tbody.appendChild(tr);
    }
  } else if (!rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = columns.length + actionCols + selectionCols;
    td.className = "admin-table-empty";
    td.textContent = "No rows yet.";
    tr.appendChild(td);
    tbody.appendChild(tr);
  } else if (!displayRows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = columns.length + actionCols + selectionCols;
    td.className = "admin-table-empty";
    td.textContent = "No rows match current filters.";
    tr.appendChild(td);
    tbody.appendChild(tr);
  } else {
    displayRows.forEach((row) => {
      const locked = isRowLocked(row);
      const tr = document.createElement("tr");
      const rowId = defaultRowId(row, options);
      if (locked) {
        tr.classList.add("admin-table-row-locked");
      }
      if (selectable) {
        const tdSel = document.createElement("td");
        tdSel.className = "admin-table-select-col";
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = selectedState.has(rowId);
        cb.addEventListener("change", () => {
          if (cb.checked) {
            selectedState.add(rowId);
          } else {
            selectedState.delete(rowId);
          }
          renderTable(container, columns, rows, options);
        });
        tdSel.appendChild(cb);
        tr.appendChild(tdSel);
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
          pill.textContent = badgeCellText(row, col);
          display.appendChild(pill);

          const applyBadge = () => {
            pill.textContent = badgeCellText(row, col);
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
                renderTable(container, columns, rows, options);
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
                renderTable(container, columns, rows, options);
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
              renderTable(container, columns, rows, options);
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
                renderTable(container, columns, rows, options);
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
                renderTable(container, columns, rows, options);
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
            pill.textContent = badgeCellText(row, col);
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

  const caret = container.__adminTextSearchCaretPending;
  if (caret && textSearchOn && Array.isArray(rows)) {
    const searchInp = wrap.querySelector(".admin-table-search-input");
    delete container.__adminTextSearchCaretPending;
    if (searchInp) {
      requestAnimationFrame(() => {
        searchInp.focus();
        try {
          const len = searchInp.value.length;
          const a = Math.max(0, Math.min(typeof caret.start === "number" ? caret.start : len, len));
          const b = Math.max(0, Math.min(typeof caret.end === "number" ? caret.end : len, len));
          searchInp.setSelectionRange(a, b);
        } catch (_e) {
          /* ignore */
        }
      });
    }
  }
}
