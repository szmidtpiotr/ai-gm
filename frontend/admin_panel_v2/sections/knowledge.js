import { adminFetch }          from "/admin_panel_v2/shared/api.js?v=3";
import { showToast }           from "/admin_panel_v2/shared/toast.js?v=2";
import { openModal, closeModal } from "/admin_panel_v2/shared/modal.js?v=2";
import { renderTable }         from "/admin_panel_v2/shared/table.js?v=5";

const CATEGORIES = ["general", "magic", "combat", "mechanics", "exploration", "economy"];

const CATEGORY_LABELS = {
  general:     "Ogólne",
  magic:       "Magia",
  combat:      "Walka",
  mechanics:   "Mechaniki",
  exploration: "Eksploracja",
  economy:     "Ekonomia",
};

export async function init(panel) {
  panel.innerHTML = `
    <div class="section-header">
      <h2>Księga Wiedzy</h2>
      <p class="section-desc">Wskazówki mechaniczne wyświetlane graczom podczas podróży i odpoczynku.</p>
    </div>
    <div id="kb-toolbar"></div>
    <div id="kb-table"></div>
  `;

  const toolbar = panel.querySelector("#kb-toolbar");
  const tableHost = panel.querySelector("#kb-table");

  const addBtn = document.createElement("button");
  addBtn.className = "primary-btn";
  addBtn.textContent = "+ Dodaj wskazówkę";
  addBtn.addEventListener("click", () => _openTipModal(null, load));
  toolbar.appendChild(addBtn);

  const load = async () => {
    renderTable(tableHost, null, null, {});
    let rows = [];
    try {
      rows = (await adminFetch("/api/admin/knowledge-book")).items || [];
    } catch (e) {
      showToast("Błąd ładowania: " + (e.message || "?"), "error");
      return;
    }

    const cols = [
      { key: "tip_key",    label: "Klucz",      editable: false },
      { key: "category",   label: "Kategoria",
        type: "badge", editType: "select",
        editOptions: CATEGORIES,
        formatDisplay: (r) => CATEGORY_LABELS[r.category] || r.category,
        badgeClass: (r) => ({
          magic: "admin-badge-blue", combat: "admin-badge-red",
          mechanics: "admin-badge-green", exploration: "admin-badge-blue",
          economy: "admin-badge-green",
        }[r.category] || "admin-badge-blue"),
      },
      { key: "title",      label: "Tytuł",      editable: true },
      { key: "body",       label: "Treść",       editable: true, popup: true },
      { key: "sort_order", label: "Kolejność",   type: "number", editable: true },
      { key: "is_active",  label: "Aktywna",     type: "boolean", editable: true },
    ];

    renderTable(tableHost, cols, rows, {
      tableId: "knowledge-book",
      selectable: false,
      showTextSearch: true,
      searchPlaceholder: "Szukaj wskazówek…",
      async onEdit(row, colKey, newVal) {
        try {
          await adminFetch(`/api/admin/knowledge-book/${row.tip_key}`, {
            method: "PATCH", body: JSON.stringify({ [colKey]: newVal }),
          });
          showToast("Zapisano.", "success");
          await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      async onDelete(row) {
        try {
          await adminFetch(`/api/admin/knowledge-book/${row.tip_key}`, { method: "DELETE" });
          showToast("Usunięto.", "success");
          await load();
        } catch (e) { showToast("Błąd: " + (e.message || "?"), "error"); throw e; }
      },
      extraActions: (row) => [{ label: "Edytuj", class: "secondary-btn", onClick: () => _openTipModal(row, load) }],
    });
  };

  await load();
}

function _openTipModal(row, onDone) {
  const isEdit = !!row;

  const form = document.createElement("div");
  form.className = "modal-form";
  form.innerHTML = `
    <label class="modal-field"><span>Klucz *</span>
      <input name="tip_key" type="text" value="${_esc(row?.tip_key ?? "")}" ${isEdit ? "readonly" : ""}
             placeholder="np. spell_rank_progression" autocomplete="off"/>
    </label>
    <label class="modal-field"><span>Tytuł *</span>
      <input name="title" type="text" value="${_esc(row?.title ?? "")}" placeholder="Mistrzostwo przez praktykę" autocomplete="off"/>
    </label>
    <label class="modal-field"><span>Kategoria</span>
      <select name="category">
        ${CATEGORIES.map(c => `<option value="${c}" ${(row?.category ?? "general") === c ? "selected" : ""}>${CATEGORY_LABELS[c]}</option>`).join("")}
      </select>
    </label>
    <label class="modal-field"><span>Treść *</span>
      <textarea name="body" rows="5" placeholder="Treść wskazówki wyświetlanej graczowi…">${_esc(row?.body ?? "")}</textarea>
    </label>
    <label class="modal-field"><span>Kolejność wyświetlania</span>
      <input name="sort_order" type="number" value="${row?.sort_order ?? 0}" min="0" step="10"/>
    </label>
    <label class="modal-checkbox-row">
      <input name="is_active" type="checkbox" ${(row?.is_active ?? 1) ? "checked" : ""}>
      <span>Aktywna (wyświetlana graczom)</span>
    </label>
  `;

  openModal({
    title: isEdit ? `Edytuj: ${row.tip_key}` : "Nowa wskazówka",
    content: form,
    footer: [
      { label: "Anuluj", class: "secondary-btn", onClick: (c) => c() },
      { label: isEdit ? "Zapisz" : "Dodaj", class: "primary-btn", onClick: async (c) => {
          const g = (n) => form.querySelector(`[name="${n}"]`);
          const tip_key = g("tip_key").value.trim();
          const title   = g("title").value.trim();
          const body    = g("body").value.trim();
          if (!tip_key || !title || !body) { showToast("Klucz, tytuł i treść są wymagane.", "error"); return; }
          const payload = {
            tip_key, title, body,
            category:   g("category").value,
            sort_order: parseInt(g("sort_order").value) || 0,
            is_active:  g("is_active").checked ? 1 : 0,
          };
          try {
            if (isEdit) {
              await adminFetch(`/api/admin/knowledge-book/${row.tip_key}`, {
                method: "PATCH", body: JSON.stringify(payload),
              });
            } else {
              await adminFetch("/api/admin/knowledge-book", {
                method: "POST", body: JSON.stringify(payload),
              });
            }
            showToast(isEdit ? "Zapisano." : "Dodano wskazówkę.", "success");
            c();
            await onDone();
          } catch (e) { showToast(e.message || "Błąd zapisu", "error"); }
        }},
    ],
  });
}

function _esc(s) {
  return String(s ?? "").replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
