import { adminFetch, APIError } from "/admin_panel/shared/api.js?v=17";
import { showToast } from "/admin_panel/shared/toast.js?v=17";
import { showConfirm } from "/admin_panel/shared/table.js?v=20";
import { openModal } from "/admin_panel/shared/modal.js?v=17";

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) {
    n.className = cls;
  }
  if (text !== undefined && text !== null) {
    n.textContent = text;
  }
  return n;
}

function parseApiError(err, fallback) {
  if (err instanceof APIError && err.body && typeof err.body === "object" && err.body.detail) {
    return String(err.body.detail);
  }
  return fallback;
}

function mergeCounts(row, patch) {
  const c = row.characters_count;
  const p = row.campaigns_count;
  Object.assign(row, patch);
  if (patch.characters_count === undefined) {
    row.characters_count = c;
  }
  if (patch.campaigns_count === undefined) {
    row.campaigns_count = p;
  }
}

/**
 * @param {HTMLElement} container
 */
export async function init(container) {
  container.innerHTML = "";
  container.classList.add("accounts-section");

  const toolbar = el("div", "accounts-toolbar");
  const h2 = el("h2", "accounts-heading", "Accounts");
  const addBtn = el("button", "primary-btn", "Add User");
  addBtn.type = "button";
  toolbar.appendChild(h2);
  toolbar.appendChild(addBtn);

  const tableHost = el("div", "accounts-table-host");
  container.appendChild(toolbar);
  container.appendChild(tableHost);

  /** @type {Array<Record<string, unknown>>} */
  let rows = [];
  let openDetailUserId = null;
  /** @type {HTMLTableRowElement | null} */
  let detailRowEl = null;

  function closeDetail() {
    if (detailRowEl && detailRowEl.parentNode) {
      detailRowEl.remove();
    }
    detailRowEl = null;
    openDetailUserId = null;
  }

  async function patchAccount(row, body) {
    const data = await adminFetch(`/api/admin/accounts/${row.id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    const item = data.item || {};
    mergeCounts(row, item);
  }

  function renderMainTable() {
    closeDetail();
    tableHost.innerHTML = "";
    const wrap = el("div", "admin-table-wrap");
    const table = el("table", "admin-table user-table");
    const thead = el("thead");
    const hr = el("tr");
    ["ID", "Username", "Display Name", "Role", "Active", "Characters", "Campaigns", "Actions"].forEach((lab) => {
      const th = el("th", "", lab);
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    table.appendChild(thead);
    const tbody = el("tbody");

    if (!rows.length) {
      const tr = el("tr");
      const td = el("td", "admin-table-empty", "No accounts yet.");
      td.colSpan = 8;
      tr.appendChild(td);
      tbody.appendChild(tr);
    } else {
      rows.forEach((row) => {
        const tr = el("tr", "user-row");
        tr.dataset.userId = String(row.id);

        const tdId = el("td", "admin-table-cell-readonly", String(row.id));
        tr.appendChild(tdId);

        const tdUser = el("td", "admin-table-cell-readonly", String(row.username || ""));
        tr.appendChild(tdUser);

        const tdDisp = el("td");
        const dispHost = el("div", "admin-table-cell-edit-host");
        const dispSpan = el("span", "admin-table-cell-text", String(row.display_name ?? ""));
        dispHost.appendChild(dispSpan);
        dispSpan.addEventListener("click", () => {
          if (dispHost.querySelector("input")) {
            return;
          }
          const inp = el("input", "admin-table-cell-input");
          inp.type = "text";
          inp.value = String(row.display_name ?? "");
          let committed = false;
          const cancel = () => {
            dispSpan.textContent = String(row.display_name ?? "");
            inp.remove();
            dispHost.classList.remove("is-editing");
          };
          const save = async () => {
            if (committed) {
              return;
            }
            committed = true;
            const nv = inp.value.trim();
            try {
              await patchAccount(row, { display_name: nv });
              row.display_name = nv;
              dispSpan.textContent = nv;
              showToast("Display name updated.", "success");
            } catch (e) {
              showToast(parseApiError(e, "Update failed."), "error");
              committed = false;
              cancel();
              return;
            }
            inp.remove();
            dispHost.classList.remove("is-editing");
          };
          dispSpan.textContent = "";
          dispSpan.appendChild(inp);
          dispHost.classList.add("is-editing");
          inp.focus();
          inp.select();
          inp.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter") {
              ev.preventDefault();
              void save();
            } else if (ev.key === "Escape") {
              ev.preventDefault();
              committed = true;
              cancel();
            }
          });
          inp.addEventListener("blur", () => {
            setTimeout(() => {
              if (!committed) {
                void save();
              }
            }, 0);
          });
        });
        tdDisp.appendChild(dispHost);
        tr.appendChild(tdDisp);

        const tdRole = el("td");
        const roleBtn = el("button", "role-badge");
        roleBtn.type = "button";
        function syncRoleUi() {
          const adm = Number(row.is_admin) === 1;
          roleBtn.classList.toggle("role-badge-admin", adm);
          roleBtn.classList.toggle("role-badge-player", !adm);
          roleBtn.textContent = adm ? "Admin" : "Player";
        }
        syncRoleUi();
        roleBtn.addEventListener("click", async () => {
          const curAdm = Number(row.is_admin) === 1;
          const next = curAdm ? 0 : 1;
          const msg = next
            ? `Grant admin access to ${row.username}?`
            : `Revoke admin access from ${row.username}?`;
          const ok = await showConfirm(msg);
          if (!ok) {
            return;
          }
          try {
            await patchAccount(row, { is_admin: next });
            row.is_admin = next;
            syncRoleUi();
            showToast(next ? "Admin access granted." : "Admin access revoked.", "success");
          } catch (e) {
            showToast(parseApiError(e, "Role update failed."), "error");
          }
        });
        tdRole.appendChild(roleBtn);
        tr.appendChild(tdRole);

        const tdAct = el("td");
        const actBtn = el("button", "toggle-btn");
        actBtn.type = "button";
        function syncActiveUi() {
          actBtn.textContent = Number(row.is_active) === 1 ? "✅" : "❌";
        }
        syncActiveUi();
        actBtn.addEventListener("click", async () => {
          const cur = Number(row.is_active) === 1;
          const next = cur ? 0 : 1;
          try {
            await patchAccount(row, { is_active: next });
            row.is_active = next;
            syncActiveUi();
            showToast(next ? "User activated." : "User deactivated.", "success");
          } catch (e) {
            showToast(parseApiError(e, "Active toggle failed."), "error");
          }
        });
        tdAct.appendChild(actBtn);
        tr.appendChild(tdAct);

        tr.appendChild(el("td", "admin-table-cell-readonly", String(row.characters_count ?? 0)));
        tr.appendChild(el("td", "admin-table-cell-readonly", String(row.campaigns_count ?? 0)));

        const tdActions = el("td", "admin-table-actions");
        const viewBtn = el("button", "secondary-btn", "👁 View");
        viewBtn.type = "button";
        viewBtn.addEventListener("click", () => {
          const uid = Number(row.id);
          if (openDetailUserId === uid && detailRowEl) {
            closeDetail();
            return;
          }
          closeDetail();
          openDetailUserId = uid;
          const dtr = el("tr", "detail-panel-row");
          const dtd = el("td", "detail-panel");
          dtd.colSpan = 8;
          dtr.appendChild(dtd);
          tr.insertAdjacentElement("afterend", dtr);
          detailRowEl = dtr;
          mountUserDetail(dtd, row);
        });
        const delBtn = el("button", "secondary-btn danger-outline", "🗑 Delete");
        delBtn.type = "button";
        delBtn.addEventListener("click", async () => {
          const ok = await showConfirm("Soft-delete user? This sets them inactive.", { dangerous: true });
          if (!ok) {
            return;
          }
          try {
            await adminFetch(`/api/admin/accounts/${row.id}`, { method: "DELETE" });
            rows = rows.filter((r) => r.id !== row.id);
            showToast("User deactivated.", "success");
            renderMainTable();
          } catch (e) {
            showToast(parseApiError(e, "Delete failed."), "error");
          }
        });
        tdActions.appendChild(viewBtn);
        tdActions.appendChild(delBtn);
        tr.appendChild(tdActions);

        tbody.appendChild(tr);
      });
    }

    table.appendChild(tbody);
    wrap.appendChild(table);
    tableHost.appendChild(wrap);
  }

  async function refreshList() {
    closeDetail();
    try {
      const data = await adminFetch("/api/admin/accounts");
      rows = (data.items || []).map((r) => ({ ...r }));
      renderMainTable();
    } catch (e) {
      showToast(parseApiError(e, "Failed to load accounts."), "error");
      rows = [];
      renderMainTable();
    }
  }

  function openAddUserModal() {
    const form = el("div", "accounts-add-form");
    const u = el("input", "");
    u.type = "text";
    u.placeholder = "Username";
    const p = el("input", "");
    p.type = "password";
    p.placeholder = "Password (min 8 chars)";
    const d = el("input", "");
    d.type = "text";
    d.placeholder = "Display name (optional)";
    const role = el("select", "");
    role.innerHTML = '<option value="0">Player</option><option value="1">Admin</option>';
    ["Username", "Password", "Display name", "Role"].forEach((label, i) => {
      const wrap = el("div", "field");
      const lb = el("label", "", label);
      const inputs = [u, p, d, role];
      wrap.appendChild(lb);
      wrap.appendChild(inputs[i]);
      form.appendChild(wrap);
    });

    openModal({
      title: "Add User",
      content: form,
      footer: [
        {
          label: "Cancel",
          class: "secondary-btn",
          onClick: (close) => close(),
        },
        {
          label: "Create",
          class: "primary-btn",
          onClick: async (close) => {
            try {
              const body = {
                username: u.value.trim(),
                password: p.value,
                display_name: d.value.trim() || null,
                is_admin: Number(role.value),
              };
              const res = await adminFetch("/api/admin/accounts/create", {
                method: "POST",
                body: JSON.stringify(body),
              });
              rows.push({
                id: res.id,
                username: res.username,
                display_name: res.display_name,
                is_admin: res.is_admin,
                is_active: res.is_active,
                created_at: res.created_at,
                characters_count: 0,
                campaigns_count: 0,
              });
              showToast("User created.", "success");
              close();
              renderMainTable();
            } catch (e) {
              showToast(parseApiError(e, "Create failed."), "error");
            }
          },
        },
      ],
    });
  }

  addBtn.addEventListener("click", () => openAddUserModal());

  await refreshList();
}

/**
 * @param {HTMLElement} host
 * @param {Record<string, unknown>} userRow
 */
function mountUserDetail(host, userRow) {
  const uid = Number(userRow.id);
  const tabs = el("div", "detail-sub-tabs sub-tabs");
  const llmBtn = el("button", "sub-tab-btn active", "🔧 LLM Config");
  const campBtn = el("button", "sub-tab-btn", "🗺 Kampanie");
  const charBtn = el("button", "sub-tab-btn", "🧙 Postacie");
  llmBtn.type = "button";
  campBtn.type = "button";
  charBtn.type = "button";
  tabs.appendChild(llmBtn);
  tabs.appendChild(campBtn);
  tabs.appendChild(charBtn);

  const body = el("div", "detail-panel-body");
  host.appendChild(tabs);
  host.appendChild(body);

  const panels = {
    llm: el("div", "detail-sub-panel"),
    campaigns: el("div", "detail-sub-panel"),
    characters: el("div", "detail-sub-panel"),
  };
  panels.campaigns.hidden = true;
  panels.characters.hidden = true;
  body.appendChild(panels.llm);
  body.appendChild(panels.campaigns);
  body.appendChild(panels.characters);

  function activate(tab) {
    llmBtn.classList.toggle("active", tab === "llm");
    campBtn.classList.toggle("active", tab === "campaigns");
    charBtn.classList.toggle("active", tab === "characters");
    panels.llm.hidden = tab !== "llm";
    panels.campaigns.hidden = tab !== "campaigns";
    panels.characters.hidden = tab !== "characters";
  }

  llmBtn.addEventListener("click", () => {
    activate("llm");
    void mountLlm(uid, panels.llm);
  });
  campBtn.addEventListener("click", () => {
    activate("campaigns");
    void mountCampaigns(uid, panels.campaigns);
  });
  charBtn.addEventListener("click", () => {
    activate("characters");
    void mountCharacters(uid, panels.characters);
  });

  activate("llm");
  void mountLlm(uid, panels.llm);
}

async function mountLlm(userId, host) {
  host.innerHTML = "";
  const wrap = el("div", "accounts-llm-form");
  try {
    const data = await adminFetch(`/api/admin/users/${userId}/llm-settings`);
    const s = data.settings || {};
    const prov = el("select", "");
    prov.innerHTML =
      '<option value="ollama">ollama</option><option value="openai">openai</option><option value="custom">custom</option>';
    prov.value = String(s.provider || "ollama").toLowerCase();
    const base = el("input", "");
    base.type = "text";
    base.value = String(s.base_url || "");
    const model = el("input", "");
    model.type = "text";
    model.value = String(s.model || "");
    const apiKey = el("input", "");
    apiKey.type = "password";
    apiKey.placeholder = "••••••• (masked)";
    apiKey.value = "";

    [["Provider", prov], ["Base URL", base], ["Model", model], ["API Key", apiKey]].forEach(([label, inp]) => {
      const f = el("div", "field");
      f.appendChild(el("label", "", String(label)));
      f.appendChild(inp);
      wrap.appendChild(f);
    });

    const save = el("button", "primary-btn", "Save");
    save.type = "button";
    save.addEventListener("click", async () => {
      const body = {
        provider: prov.value.trim().toLowerCase(),
        base_url: base.value.trim(),
        model: model.value.trim(),
      };
      if (apiKey.value.trim()) {
        body.api_key = apiKey.value;
      }
      try {
        await adminFetch(`/api/admin/users/${userId}/llm-settings`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
        showToast("LLM settings saved.", "success");
        apiKey.value = "";
      } catch (e) {
        showToast(parseApiError(e, "Save failed."), "error");
      }
    });
    wrap.appendChild(save);
    host.appendChild(wrap);
  } catch (e) {
    host.appendChild(el("p", "muted", parseApiError(e, "Failed to load LLM settings.")));
  }
}

async function mountCampaigns(userId, host) {
  host.innerHTML = "";
  try {
    const data = await adminFetch(`/api/admin/campaigns?owner_id=${encodeURIComponent(String(userId))}`);
    const items = data.items || [];
    if (!items.length) {
      host.appendChild(el("p", "muted", "No campaigns for this user."));
      return;
    }
    const wrap = el("div", "admin-table-wrap");
    const table = el("table", "admin-table");
    const thead = el("thead");
    const hr = el("tr");
    ["ID", "Title", "Status", "Turns", "Last Turn", "Actions"].forEach((h) => {
      hr.appendChild(el("th", "", h));
    });
    thead.appendChild(hr);
    table.appendChild(thead);
    const tb = el("tbody");
    items.forEach((c) => {
      const tr = el("tr");
      tr.appendChild(el("td", "", String(c.id)));
      tr.appendChild(el("td", "", String(c.title ?? "")));
      tr.appendChild(el("td", "", String(c.status ?? "")));
      tr.appendChild(el("td", "", String(c.turn_count ?? 0)));
      tr.appendChild(el("td", "", c.last_turn_at != null ? String(c.last_turn_at) : "—"));
      const td = el("td", "admin-table-actions");
      const regen = el("button", "secondary-btn", "🔄 Regen Summary");
      regen.type = "button";
      regen.addEventListener("click", async () => {
        const label = regen.textContent;
        regen.disabled = true;
        regen.textContent = "⏳";
        try {
          await adminFetch(`/api/admin/campaigns/${c.id}/regenerate-summary`, { method: "POST" });
          showToast("Summary regeneration finished.", "success");
        } catch (e) {
          showToast(parseApiError(e, "Regeneration failed."), "error");
        } finally {
          regen.disabled = false;
          regen.textContent = label;
        }
      });
      td.appendChild(regen);
      tr.appendChild(td);
      tb.appendChild(tr);
    });
    table.appendChild(tb);
    wrap.appendChild(table);
    host.appendChild(wrap);
  } catch (e) {
    host.appendChild(el("p", "muted", parseApiError(e, "Failed to load campaigns.")));
  }
}

async function mountCharacters(userId, host) {
  host.innerHTML = "";
  /** @type {HTMLTableRowElement | null} */
  let sheetEditorRow = null;

  async function load() {
    host.innerHTML = "";
    sheetEditorRow = null;
    try {
      const data = await adminFetch(`/api/admin/characters?owner_id=${encodeURIComponent(String(userId))}`);
      const items = data.items || [];
      if (!items.length) {
        host.appendChild(el("p", "muted", "No characters for this user."));
        return;
      }
      const wrap = el("div", "admin-table-wrap");
      const table = el("table", "admin-table");
      const thead = el("thead");
      const hr = el("tr");
      ["ID", "Name", "Campaign", "Actions"].forEach((h) => {
        hr.appendChild(el("th", "", h));
      });
      thead.appendChild(hr);
      table.appendChild(thead);
      const tb = el("tbody");

      items.forEach((ch) => {
        const tr = el("tr", "char-row");
        tr.dataset.charId = String(ch.id);
        tr.appendChild(el("td", "", String(ch.id)));
        tr.appendChild(el("td", "", String(ch.name ?? "")));
        tr.appendChild(el("td", "", String(ch.campaign_title ?? "")));
        const td = el("td", "admin-table-actions");
        const editBtn = el("button", "secondary-btn", "📋 Edit Sheet");
        editBtn.type = "button";
        editBtn.addEventListener("click", () => {
          if (sheetEditorRow && sheetEditorRow.parentNode) {
            const prevFor = sheetEditorRow.dataset.editorFor;
            sheetEditorRow.remove();
            sheetEditorRow = null;
            if (prevFor === String(ch.id)) {
              return;
            }
          }
          const er = el("tr", "sheet-editor-row");
          er.dataset.editorFor = String(ch.id);
          const ec = el("td", "");
          ec.colSpan = 4;
          const err = el("div", "sheet-editor-error");
          err.hidden = true;
          const ta = el("textarea", "sheet-editor");
          ta.rows = 16;
          try {
            const raw = ch.sheet_json;
            let parsed = {};
            if (typeof raw === "string") {
              parsed = JSON.parse(raw || "{}");
            } else if (raw && typeof raw === "object") {
              parsed = raw;
            }
            ta.value = JSON.stringify(parsed, null, 2);
          } catch (_e) {
            ta.value = String(ch.sheet_json || "{}");
          }
          const rowBtns = el("div", "sheet-editor-actions");
          const saveBtn = el("button", "primary-btn", "💾 Save & Recreate");
          saveBtn.type = "button";
          const cancelBtn = el("button", "secondary-btn", "✖ Cancel");
          cancelBtn.type = "button";
          saveBtn.addEventListener("click", async () => {
            err.hidden = true;
            err.textContent = "";
            let sheetJson;
            try {
              sheetJson = JSON.parse(ta.value);
            } catch (e) {
              err.textContent = `Invalid JSON: ${e.message || e}`;
              err.hidden = false;
              return;
            }
            try {
              await adminFetch(`/api/admin/characters/${ch.id}/recreate`, {
                method: "POST",
                body: JSON.stringify({
                  sheet_json: sheetJson,
                  name: ch.name,
                  clear_inventory: false,
                }),
              });
              showToast("Character sheet recreated.", "success");
              ch.sheet_json = JSON.stringify(sheetJson);
              er.remove();
              sheetEditorRow = null;
              void load();
            } catch (e2) {
              showToast(parseApiError(e2, "Recreate failed."), "error");
            }
          });
          cancelBtn.addEventListener("click", () => {
            er.remove();
            sheetEditorRow = null;
          });
          ec.appendChild(err);
          ec.appendChild(ta);
          rowBtns.appendChild(saveBtn);
          rowBtns.appendChild(cancelBtn);
          ec.appendChild(rowBtns);
          er.appendChild(ec);
          sheetEditorRow = er;
          tr.insertAdjacentElement("afterend", er);
        });
        const delBtn = el("button", "secondary-btn danger-outline", "🗑 Delete");
        delBtn.type = "button";
        delBtn.addEventListener("click", async () => {
          const ok = await showConfirm("Delete character and all their campaign turns?", { dangerous: true });
          if (!ok) {
            return;
          }
          try {
            await adminFetch(`/api/admin/characters/${ch.id}`, { method: "DELETE" });
            showToast("Character deleted.", "success");
            void load();
          } catch (e) {
            showToast(parseApiError(e, "Delete failed."), "error");
          }
        });
        td.appendChild(editBtn);
        td.appendChild(delBtn);
        tr.appendChild(td);
        tb.appendChild(tr);
      });
      table.appendChild(tb);
      wrap.appendChild(table);
      host.appendChild(wrap);
    } catch (e) {
      host.appendChild(el("p", "muted", parseApiError(e, "Failed to load characters.")));
    }
  }

  void load();
}
