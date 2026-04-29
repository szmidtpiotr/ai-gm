import { adminFetch, APIError } from "/admin_panel/shared/api.js?v=19";
import { showToast } from "/admin_panel/shared/toast.js?v=19";
import { showConfirm } from "/admin_panel/shared/table.js?v=23";
import { openModal } from "/admin_panel/shared/modal.js?v=19";

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = text;
  return n;
}

function parseApiError(err, fallback) {
  if (err instanceof APIError && err.body && typeof err.body === "object" && err.body.detail) {
    return String(err.body.detail);
  }
  return fallback;
}

function splitLocationKeys(raw) {
  return String(raw || "")
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function prettyJson(raw, fallback) {
  const src = String(raw ?? fallback ?? "");
  try {
    return JSON.stringify(JSON.parse(src || fallback || "{}"), null, 2);
  } catch (_e) {
    return src || fallback || "";
  }
}

/**
 * @param {HTMLElement} container
 */
export async function init(container) {
  container.innerHTML = "";
  container.classList.add("accounts-section");

  const toolbar = el("div", "accounts-toolbar");
  const title = el("h2", "accounts-heading", "NPC");
  const addBtn = el("button", "primary-btn", "+ Nowy NPC");
  addBtn.type = "button";
  toolbar.appendChild(title);
  toolbar.appendChild(addBtn);

  const host = el("div", "accounts-table-host");
  container.appendChild(toolbar);
  container.appendChild(host);

  /** @type {Array<Record<string, any>>} */
  let rows = [];

  function renderTable() {
    host.innerHTML = "";
    const wrap = el("div", "admin-table-wrap");
    const table = el("table", "admin-table");
    const thead = el("thead");
    const hr = el("tr");
    ["ID", "Key", "Label", "Typ", "Lokacje", "Sklep", "Aktywny", "Akcje"].forEach((h) => {
      hr.appendChild(el("th", "", h));
    });
    thead.appendChild(hr);
    table.appendChild(thead);

    const tbody = el("tbody");
    if (!rows.length) {
      const tr = el("tr");
      const td = el("td", "admin-table-empty", "Brak NPC.");
      td.colSpan = 8;
      tr.appendChild(td);
      tbody.appendChild(tr);
    } else {
      rows.forEach((npc) => {
        const tr = el("tr");
        tr.appendChild(el("td", "admin-table-cell-readonly", String(npc.id)));
        tr.appendChild(el("td", "admin-table-cell-readonly", String(npc.key || "")));
        tr.appendChild(el("td", "", String(npc.label || "")));
        tr.appendChild(el("td", "", String(npc.npc_type || "")));
        const locs = Array.isArray(npc.location_keys) ? npc.location_keys : [];
        tr.appendChild(el("td", "", locs.length ? locs.join(", ") : "—"));
        tr.appendChild(el("td", "", Number(npc.is_shop) === 1 ? "✅" : "—"));
        tr.appendChild(el("td", "", Number(npc.is_active) === 1 ? "✅" : "❌"));

        const tdActions = el("td", "admin-table-actions");
        const editBtn = el("button", "secondary-btn", "Edytuj");
        editBtn.type = "button";
        editBtn.addEventListener("click", () => openNpcForm(npc));
        const delBtn = el("button", "secondary-btn danger-outline", "Usuń");
        delBtn.type = "button";
        delBtn.addEventListener("click", async () => {
          const ok = await showConfirm(`Usunąć NPC "${npc.label || npc.key}"?`, { dangerous: true });
          if (!ok) return;
          try {
            await adminFetch(`/api/npcs/${npc.id}`, { method: "DELETE" });
            showToast("NPC usunięty.", "success");
            await refreshNpcs();
          } catch (e) {
            showToast(parseApiError(e, "Delete failed."), "error");
          }
        });
        tdActions.appendChild(editBtn);
        tdActions.appendChild(delBtn);
        tr.appendChild(tdActions);
        tbody.appendChild(tr);
      });
    }

    table.appendChild(tbody);
    wrap.appendChild(table);
    host.appendChild(wrap);
  }

  async function refreshNpcs() {
    try {
      const data = await adminFetch("/api/npcs");
      rows = Array.isArray(data?.data) ? data.data : [];
    } catch (e) {
      rows = [];
      showToast(parseApiError(e, "Failed to load NPCs."), "error");
    }
    renderTable();
  }

  async function saveNpc(npcId, body) {
    const path = npcId ? `/api/npcs/${npcId}` : "/api/npcs";
    const method = npcId ? "PATCH" : "POST";
    await adminFetch(path, {
      method,
      body: JSON.stringify(body),
    });
  }

  function openNpcForm(npc = null) {
    const edit = !!npc;
    const form = el("div", "accounts-add-form");

    const key = el("input", "");
    key.type = "text";
    key.placeholder = "merchant_aldric";
    key.value = String(npc?.key || "");
    key.disabled = edit;

    const label = el("input", "");
    label.type = "text";
    label.value = String(npc?.label || "");

    const npcType = el("select", "");
    npcType.innerHTML =
      '<option value="neutral">neutral</option><option value="merchant">merchant</option><option value="quest_giver">quest_giver</option><option value="ally">ally</option>';
    npcType.value = String(npc?.npc_type || "neutral");

    const description = el("textarea", "");
    description.rows = 3;
    description.value = String(npc?.description || "");

    const isShopWrap = el("label", "");
    const isShop = el("input", "");
    isShop.type = "checkbox";
    isShop.checked = Number(npc?.is_shop || 0) === 1;
    isShopWrap.appendChild(isShop);
    isShopWrap.appendChild(document.createTextNode(" NPC prowadzi sklep"));

    const personality = el("textarea", "");
    personality.rows = 6;
    personality.value = prettyJson(npc?.personality_json, "{}");

    const shopInv = el("textarea", "");
    shopInv.rows = 6;
    shopInv.value = prettyJson(npc?.shop_inventory_json, "[]");

    const locKeys = el("textarea", "");
    locKeys.rows = 4;
    locKeys.placeholder = "Jedna lokacja na linię, np.\nvillage_square\ninn_main";
    locKeys.value = Array.isArray(npc?.location_keys) ? npc.location_keys.join("\n") : "";

    const activeWrap = el("label", "");
    const isActive = el("input", "");
    isActive.type = "checkbox";
    isActive.checked = Number(npc?.is_active ?? 1) === 1;
    activeWrap.appendChild(isActive);
    activeWrap.appendChild(document.createTextNode(" Aktywny"));

    const fields = [
      ["Key", key],
      ["Label", label],
      ["Typ", npcType],
      ["Opis", description],
      ["Sklep", isShopWrap],
      ["Personality JSON", personality],
      ["Shop inventory JSON", shopInv],
      ["Location keys (newline)", locKeys],
      ["Status", activeWrap],
    ];
    fields.forEach(([name, ctrl]) => {
      const w = el("div", "field");
      w.appendChild(el("label", "", String(name)));
      w.appendChild(ctrl);
      form.appendChild(w);
    });

    const syncShopFieldState = () => {
      shopInv.disabled = !isShop.checked;
      shopInv.style.opacity = isShop.checked ? "1" : "0.6";
    };
    syncShopFieldState();
    isShop.addEventListener("change", syncShopFieldState);

    const submit = async (close) => {
      if (!edit && !key.value.trim()) {
        showToast("Key jest wymagany.", "error");
        return;
      }
      if (!label.value.trim()) {
        showToast("Label jest wymagany.", "error");
        return;
      }

      try {
        JSON.parse(personality.value || "{}");
      } catch (e) {
        showToast(`Invalid JSON in personality_json: ${e.message || e}`, "error");
        return;
      }
      const shopRaw = shopInv.value || "[]";
      if (isShop.checked) {
        try {
          JSON.parse(shopRaw);
        } catch (e) {
          showToast(`Invalid JSON in shop_inventory_json: ${e.message || e}`, "error");
          return;
        }
      }

      const payload = {
        label: label.value.trim(),
        npc_type: npcType.value,
        description: description.value.trim() || null,
        personality_json: personality.value || "{}",
        is_shop: isShop.checked ? 1 : 0,
        shop_inventory_json: isShop.checked ? shopRaw : "[]",
        is_active: isActive.checked ? 1 : 0,
        location_keys: splitLocationKeys(locKeys.value),
      };
      if (!edit) payload.key = key.value.trim();

      try {
        await saveNpc(edit ? Number(npc.id) : null, payload);
        showToast(edit ? "NPC zaktualizowany." : "NPC utworzony.", "success");
        close();
        await refreshNpcs();
      } catch (e) {
        showToast(parseApiError(e, "Save failed."), "error");
      }
    };

    openModal({
      title: edit ? `Edytuj NPC #${npc.id}` : "Nowy NPC",
      content: form,
      footer: [
        { label: "Anuluj", class: "secondary-btn", onClick: (close) => close() },
        {
          label: edit ? "Zapisz" : "Utwórz",
          class: "primary-btn",
          onClick: async (close) => {
            await submit(close);
          },
        },
      ],
    });
  }

  addBtn.addEventListener("click", () => openNpcForm(null));
  await refreshNpcs();
}
