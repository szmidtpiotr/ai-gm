import { adminFetch, APIError } from "/admin_panel/shared/api.js?v=19";
import { showToast } from "/admin_panel/shared/toast.js?v=19";
import { showConfirm } from "/admin_panel/shared/table.js?v=23";
import { openModal } from "/admin_panel/shared/modal.js?v=19";

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

const ENDPOINT_404_HINT =
  "404 Not Found — brak endpointu na tym serwerze (stary backend bez T20?) albo zły „API Base URL” w panelu admin.";

function parseApiError(err, fallback) {
  if (err instanceof APIError) {
    const st = err.status;
    const det =
      err.body && typeof err.body === "object" && err.body.detail != null
        ? String(err.body.detail)
        : "";
    if (st === 404 && (det === "Not Found" || det === "")) {
      return ENDPOINT_404_HINT;
    }
    if (det) {
      return det;
    }
    if (st === 404) {
      return ENDPOINT_404_HINT;
    }
  }
  return fallback;
}

/** Dodatkowe komunikaty tylko dla modalu GM Plan (kampania / LLM). */
function parseGmPlanAdminError(err, fallback) {
  if (err instanceof APIError) {
    if (err.status === 401) {
      return "Brak lub nieważny token admin — zaloguj się ponownie.";
    }
    const det =
      err.body && typeof err.body === "object" && err.body.detail != null
        ? String(err.body.detail)
        : "";
    if (err.status === 502 && det) {
      return det;
    }
    if (err.status === 404 && det === "Campaign not found") {
      return "Kampania nie istnieje w bazie podłączonej do tego API (inny host / inna baza niż lista kampanii).";
    }
  }
  return parseApiError(err, fallback);
}

/**
 * LOC-4: podgląd i ręczna zmiana `game_sessions.current_location_id` (ostatnia sesja kampanii).
 * @param {number} campaignId
 * @param {string | undefined} campaignTitle
 */
async function openCampaignSessionLocationModal(campaignId, campaignTitle) {
  const info = el("div", "muted");
  info.textContent = "Loading…";
  const lbl = el("label", "", "Location (catalog)");
  lbl.style.display = "block";
  lbl.style.marginTop = "12px";
  const sel = /** @type {HTMLSelectElement} */ (el("select", "admin-input"));
  sel.disabled = true;
  const wrap = el("div", "");
  wrap.appendChild(info);
  wrap.appendChild(lbl);
  wrap.appendChild(sel);

  const title = campaignTitle?.trim()
    ? `📍 Session location — ${campaignTitle}`
    : `📍 Session location — campaign ${campaignId}`;

  openModal({
    title,
    content: wrap,
    footer: [
      {
        label: "Set location",
        class: "primary-btn",
        onClick: async (closeModal) => {
          if (sel.disabled) return;
          const v = sel.value;
          if (!v) {
            showToast("Pick a location from the list.", "info");
            return;
          }
          try {
            await adminFetch(`/api/admin/campaigns/${campaignId}/session-location`, {
              method: "PATCH",
              body: JSON.stringify({ location_id: parseInt(v, 10) }),
            });
            showToast("Session location updated.", "success");
            closeModal();
          } catch (e) {
            showToast(parseApiError(e, "PATCH failed."), "error");
          }
        },
      },
      {
        label: "Reset (null)",
        class: "secondary-btn",
        onClick: async (closeModal) => {
          try {
            await adminFetch(`/api/admin/campaigns/${campaignId}/session-location`, {
              method: "PATCH",
              body: JSON.stringify({ location_id: null }),
            });
            showToast("Session location cleared.", "success");
            closeModal();
          } catch (e) {
            showToast(parseApiError(e, "Reset failed."), "error");
          }
        },
      },
      { label: "Close", class: "secondary-btn", onClick: (closeModal) => closeModal() },
    ],
  });

  try {
    const data = await adminFetch(`/api/admin/campaigns/${campaignId}/session-location`);
    info.innerHTML = "";
    info.className = "";
    sel.disabled = false;
    const sid = data.session_id;
    const curLoc = data.current_location_id;
    const curObj = data.current;

    const pSid = el("p", "muted");
    pSid.style.marginBottom = "6px";
    pSid.textContent =
      sid != null
        ? `Session ID: ${sid}`
        : "No row in game_sessions yet — one will be created on first PATCH.";
    info.appendChild(pSid);

    if (curLoc == null) {
      const w = el("p", "");
      w.style.color = "var(--warning)";
      w.textContent =
        "⚠️ No current_location_id (fail-open when target_key misses catalog).";
      info.appendChild(w);
    }

    if (curLoc != null && !curObj) {
      const w = el("p", "");
      w.style.color = "var(--warning)";
      w.textContent = `⚠️ current_location_id=${curLoc} — not found in catalog (inactive or orphaned).`;
      info.appendChild(w);
    }

    if (curObj) {
      const ap = curObj.approved === 0 ? " (pending approval)" : "";
      info.appendChild(
        el(
          "p",
          "",
          `Current: ${curObj.label} (${curObj.location_type}) · ${curObj.key}${ap}`,
        ),
      );
    }

    sel.innerHTML = "";
    const locs = data.locations || [];
    if (!locs.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "(no locations in catalog)";
      sel.appendChild(opt);
      sel.disabled = true;
      return;
    }
    for (const loc of locs) {
      const opt = document.createElement("option");
      opt.value = String(loc.id);
      const pend = loc.approved === 0 ? " (pending)" : "";
      opt.textContent = `${loc.label} · ${loc.key} (${loc.location_type})${pend}`;
      if (curObj && Number(loc.id) === Number(curObj.id)) opt.selected = true;
      sel.appendChild(opt);
    }
  } catch (e) {
    info.innerHTML = "";
    sel.innerHTML = "";
    info.appendChild(el("p", "", parseApiError(e, "Failed to load session location.")));
  }
}

/**
 * T20: admin editor / inspector for campaigns.gm_plan_json with divergence preview.
 * @param {number} campaignId
 * @param {string | undefined} campaignTitle
 */
async function openCampaignGmPlanModal(campaignId, campaignTitle) {
  const status = el("div", "muted", "Loading…");
  const divergenceWrap = el("div", "");
  const noteLabel = el("label", "", "Advance scene note");
  noteLabel.style.display = "block";
  noteLabel.style.marginTop = "12px";
  const noteInput = /** @type {HTMLInputElement} */ (el("input", "admin-input"));
  noteInput.type = "text";
  noteInput.placeholder = "Optional note for scene_log";
  const jsonLabel = el("label", "", "GM plan JSON");
  jsonLabel.style.display = "block";
  jsonLabel.style.marginTop = "12px";
  const jsonArea = /** @type {HTMLTextAreaElement} */ (el("textarea", "admin-input"));
  jsonArea.rows = 20;
  jsonArea.spellcheck = false;
  jsonArea.style.width = "100%";
  const previewLabel = el("label", "", "Prompt preview");
  previewLabel.style.display = "block";
  previewLabel.style.marginTop = "12px";
  const preview = el("pre", "config-diff-raw");
  const wrap = el("div", "");
  wrap.appendChild(status);
  wrap.appendChild(divergenceWrap);
  wrap.appendChild(noteLabel);
  wrap.appendChild(noteInput);
  wrap.appendChild(jsonLabel);
  wrap.appendChild(jsonArea);
  wrap.appendChild(previewLabel);
  wrap.appendChild(preview);

  let currentData = null;
  let isBusy = false;
  const title = campaignTitle?.trim() ? `🧭 GM Plan — ${campaignTitle}` : `🧭 GM Plan — campaign ${campaignId}`;

  async function loadData() {
    status.textContent = "Loading…";
    divergenceWrap.innerHTML = "";
    try {
      const data = await adminFetch(`/api/admin/campaigns/${campaignId}/gm-plan`);
      currentData = data;
      status.className = "muted";
      const activeArc = data?.gm_plan_json?.active_arc_id ? ` · active arc: ${data.gm_plan_json.active_arc_id}` : "";
      const ready = data?.gm_plan_ready ? "ready" : "empty";
      status.textContent = `Campaign #${campaignId} · ${String(data?.status || "")} · plan ${ready}${activeArc}`;
      jsonArea.value = JSON.stringify(data?.gm_plan_json || {}, null, 2);
      preview.textContent = String(data?.formatted_plan || "(empty plan)");

      const div = data?.divergence;
      if (div && typeof div === "object") {
        const st = String(div.status || "");
        const cls =
          st === "diverged"
            ? "warning-banner warning-banner-red"
            : st === "mixed"
              ? "warning-banner warning-banner-orange"
              : "warning-banner warning-banner-orange";
        const box = el("div", cls);
        const head = el("strong", "", `Divergence: ${st || "n/a"}`);
        box.appendChild(head);
        box.appendChild(el("p", "", String(div.summary || "")));
        const matched = Array.isArray(div.matched_plan_tokens) && div.matched_plan_tokens.length
          ? `Matched: ${div.matched_plan_tokens.join(", ")}`
          : "Matched: none";
        const offroad = Array.isArray(div.offroad_tokens) && div.offroad_tokens.length
          ? `Off-road: ${div.offroad_tokens.join(", ")}`
          : "Off-road: none";
        box.appendChild(el("p", "muted", `${matched} · ${offroad}`));
        divergenceWrap.appendChild(box);
      }

      const cc = Number(data?.characters_count ?? 0);
      if (!Number.isNaN(cc) && cc === 0) {
        const w = el("div", "warning-banner warning-banner-orange");
        w.appendChild(
          el(
            "strong",
            "",
            "Brak postaci w tej kampanii",
          ),
        );
        w.appendChild(
          el(
            "p",
            "",
            "Regenerate initial wymaga co najmniej jednej postaci (kontekst z arkusza). Wpisz plan ręcznie (Save) albo utwórz postać w grze.",
          ),
        );
        divergenceWrap.appendChild(w);
      }
    } catch (e) {
      currentData = null;
      status.className = "";
      status.textContent = parseGmPlanAdminError(e, "Failed to load GM plan.");
      preview.textContent = "";
    }
  }

  openModal({
    title,
    content: wrap,
    footer: [
      {
        label: "Save plan",
        class: "primary-btn",
        onClick: async () => {
          if (isBusy) return;
          let parsed;
          try {
            parsed = JSON.parse(jsonArea.value || "{}");
          } catch (_e) {
            showToast("GM plan JSON is invalid.", "error");
            return;
          }
          isBusy = true;
          try {
            await adminFetch(`/api/admin/campaigns/${campaignId}/gm-plan`, {
              method: "PUT",
              body: JSON.stringify({ gm_plan_json: parsed }),
            });
            showToast("GM plan saved.", "success");
            await loadData();
          } catch (e) {
            showToast(parseApiError(e, "Save failed."), "error");
          } finally {
            isBusy = false;
          }
        },
      },
      {
        label: "Advance scene",
        class: "secondary-btn",
        onClick: async () => {
          if (isBusy) return;
          isBusy = true;
          try {
            await adminFetch(`/api/admin/campaigns/${campaignId}/gm-plan/advance-scene`, {
              method: "POST",
              body: JSON.stringify({ note: noteInput.value || "" }),
            });
            noteInput.value = "";
            showToast("Scene advanced.", "success");
            await loadData();
          } catch (e) {
            showToast(parseApiError(e, "Advance scene failed."), "error");
          } finally {
            isBusy = false;
          }
        },
      },
      {
        label: "Regenerate initial",
        class: "secondary-btn",
        onClick: async () => {
          if (isBusy) return;
          if (currentData && Number(currentData.characters_count ?? 0) === 0) {
            showToast("Najpierw utwórz postać w kampanii — bez niej nie da się zbudować kontekstu planu MG.", "info");
            return;
          }
          isBusy = true;
          try {
            await adminFetch(`/api/admin/campaigns/${campaignId}/gm-plan/regenerate-initial`, {
              method: "POST",
              body: JSON.stringify({}),
            });
            showToast("GM plan regenerated.", "success");
            await loadData();
          } catch (e) {
            showToast(parseGmPlanAdminError(e, "GM plan regeneration failed."), "error");
          } finally {
            isBusy = false;
          }
        },
      },
      {
        label: "Refresh",
        class: "secondary-btn",
        onClick: async () => {
          if (isBusy) return;
          await loadData();
        },
      },
      { label: "Close", class: "secondary-btn", onClick: (closeModal) => closeModal() },
    ],
  });

  await loadData();
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

  const globalHost = el("div", "accounts-global-llm-host");
  const tableHost = el("div", "accounts-table-host");
  container.appendChild(toolbar);
  container.appendChild(globalHost);
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

  await mountGlobalLlmSettings(globalHost);
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

/**
 * @param {unknown} data
 * @returns {Array<{ name: string }>}
 */
function normalizeModelsListResponse(data) {
  const raw = Array.isArray(data?.models) ? data.models : Array.isArray(data) ? data : [];
  return raw
    .map((m) => (typeof m === "string" ? { name: m } : m))
    .filter((m) => m && typeof m.name === "string" && m.name.trim());
}

async function mountGlobalLlmSettings(host) {
  host.innerHTML = "";
  const card = el("div", "accounts-llm-form");
  const heading = el("h3", "", "Global LLM");
  const intro = el(
    "p",
    "muted",
    "Global provider / URL / API key are managed only here. Account-level custom settings below can still override these defaults.",
  );
  const status = el("p", "muted");
  const presetSelect = el("select", "");
  const presetLabel = el("input", "");
  presetLabel.type = "text";
  presetLabel.placeholder = "Preset name";
  const provider = el("select", "");
  provider.innerHTML = '<option value="ollama">ollama</option><option value="openai">openai</option>';
  const baseUrl = el("input", "");
  baseUrl.type = "text";
  baseUrl.placeholder = "http://host:11434 or https://api.openai.com/v1";
  const model = el("input", "");
  model.type = "text";
  model.placeholder = "gemma4:e4b / gpt-4.1-mini / etc.";
  const apiKey = el("input", "");
  apiKey.type = "password";
  apiKey.placeholder = "Leave empty to keep stored key on update";

  let snapshot = null;
  let selectedPresetId = null;

  function field(label, input) {
    const wrap = el("div", "field");
    wrap.appendChild(el("label", "", label));
    wrap.appendChild(input);
    return wrap;
  }

  function currentPreset() {
    if (!snapshot || selectedPresetId == null) return null;
    return (snapshot.presets || []).find((item) => Number(item.id) === Number(selectedPresetId)) || null;
  }

  function fillFromCurrentSettings() {
    const settings = snapshot?.settings || {};
    provider.value = String(settings.provider || "ollama").toLowerCase() || "ollama";
    baseUrl.value = String(settings.base_url || "");
    model.value = String(settings.model || "");
    presetLabel.value = "";
    apiKey.value = "";
    apiKey.placeholder = settings.api_key_set
      ? "Stored API key active; enter a new one only to replace it"
      : "Paste API key if required";
  }

  function fillFromPreset(preset) {
    if (!preset) {
      fillFromCurrentSettings();
      return;
    }
    provider.value = String(preset.provider || "ollama").toLowerCase() || "ollama";
    baseUrl.value = String(preset.base_url || "");
    model.value = String(preset.model || "");
    presetLabel.value = String(preset.label || "");
    apiKey.value = "";
    apiKey.placeholder = preset.api_key_set
      ? String(preset.api_key || "Stored API key active")
      : "Paste API key if required";
  }

  function rebuildPresetOptions() {
    const activeId = snapshot?.active_preset_id != null ? Number(snapshot.active_preset_id) : null;
    presetSelect.innerHTML = "";
    const envOpt = document.createElement("option");
    envOpt.value = "";
    envOpt.textContent = "Server env / no saved preset";
    presetSelect.appendChild(envOpt);
    for (const item of snapshot?.presets || []) {
      const opt = document.createElement("option");
      opt.value = String(item.id);
      opt.textContent = item.is_active ? `${item.label} (active)` : item.label;
      presetSelect.appendChild(opt);
    }
    selectedPresetId = activeId;
    presetSelect.value = activeId != null ? String(activeId) : "";
    fillFromPreset(currentPreset());
  }

  function renderStatus() {
    const settings = snapshot?.settings || {};
    const activeLabel = snapshot?.active_preset_label ? `Preset: ${snapshot.active_preset_label}` : "Preset: server env";
    const providerText = String(settings.provider || "unknown");
    const modelText = String(settings.model || "—");
    const baseText = String(settings.base_url || "—");
    status.textContent = `${activeLabel} | provider=${providerText} | model=${modelText} | base=${baseText}`;
  }

  async function reload() {
    snapshot = await adminFetch("/api/admin/llm/global-settings");
    rebuildPresetOptions();
    renderStatus();
  }

  presetSelect.addEventListener("change", () => {
    selectedPresetId = presetSelect.value ? Number(presetSelect.value) : null;
    fillFromPreset(currentPreset());
  });

  const actions = el("div", "admin-table-actions");
  const saveNewBtn = el("button", "primary-btn", "Save New + Activate");
  saveNewBtn.type = "button";
  saveNewBtn.addEventListener("click", async () => {
    try {
      await adminFetch("/api/admin/llm/presets", {
        method: "POST",
        body: JSON.stringify({
          label: presetLabel.value.trim(),
          provider: provider.value.trim().toLowerCase(),
          base_url: baseUrl.value.trim(),
          model: model.value.trim(),
          api_key: apiKey.value.trim() || null,
          activate: true,
        }),
      });
      showToast("Global LLM preset saved and activated.", "success");
      await reload();
    } catch (e) {
      showToast(parseApiError(e, "Failed to save preset."), "error");
    }
  });
  actions.appendChild(saveNewBtn);

  const updateBtn = el("button", "secondary-btn", "Update Selected + Activate");
  updateBtn.type = "button";
  updateBtn.addEventListener("click", async () => {
    if (!selectedPresetId) {
      showToast("Select a saved preset first.", "info");
      return;
    }
    try {
      await adminFetch("/api/admin/llm/presets", {
        method: "POST",
        body: JSON.stringify({
          preset_id: selectedPresetId,
          label: presetLabel.value.trim(),
          provider: provider.value.trim().toLowerCase(),
          base_url: baseUrl.value.trim(),
          model: model.value.trim(),
          api_key: apiKey.value.trim() || null,
          activate: true,
        }),
      });
      showToast("Global LLM preset updated and activated.", "success");
      await reload();
    } catch (e) {
      showToast(parseApiError(e, "Failed to update preset."), "error");
    }
  });
  actions.appendChild(updateBtn);

  const activateBtn = el("button", "secondary-btn", "Activate Selected");
  activateBtn.type = "button";
  activateBtn.addEventListener("click", async () => {
    if (!selectedPresetId) {
      showToast("Select a saved preset first.", "info");
      return;
    }
    try {
      await adminFetch(`/api/admin/llm/presets/${selectedPresetId}/activate`, {
        method: "POST",
      });
      showToast("Global LLM preset activated.", "success");
      await reload();
    } catch (e) {
      showToast(parseApiError(e, "Activation failed."), "error");
    }
  });
  actions.appendChild(activateBtn);

  const envBtn = el("button", "secondary-btn", "Use Server Env");
  envBtn.type = "button";
  envBtn.addEventListener("click", async () => {
    try {
      await adminFetch("/api/admin/llm/use-env", { method: "POST" });
      showToast("Global LLM reverted to server env.", "success");
      await reload();
    } catch (e) {
      showToast(parseApiError(e, "Could not switch to server env."), "error");
    }
  });
  actions.appendChild(envBtn);

  const deleteBtn = el("button", "secondary-btn danger-outline", "Delete Selected");
  deleteBtn.type = "button";
  deleteBtn.addEventListener("click", async () => {
    if (!selectedPresetId) {
      showToast("Select an inactive preset to delete.", "info");
      return;
    }
    const chosen = currentPreset();
    const ok = await showConfirm(`Delete preset "${chosen?.label || selectedPresetId}"?`, { dangerous: true });
    if (!ok) return;
    try {
      await adminFetch(`/api/admin/llm/presets/${selectedPresetId}`, { method: "DELETE" });
      showToast("Preset deleted.", "success");
      await reload();
    } catch (e) {
      showToast(parseApiError(e, "Delete failed."), "error");
    }
  });
  actions.appendChild(deleteBtn);

  card.appendChild(heading);
  card.appendChild(intro);
  card.appendChild(status);
  card.appendChild(field("Saved presets", presetSelect));
  card.appendChild(field("Preset label", presetLabel));
  card.appendChild(field("Provider", provider));
  card.appendChild(field("Base URL", baseUrl));
  card.appendChild(field("Model", model));
  card.appendChild(field("API Key", apiKey));
  card.appendChild(actions);
  host.appendChild(card);

  try {
    await reload();
  } catch (e) {
    host.innerHTML = "";
    host.appendChild(el("p", "muted", parseApiError(e, "Failed to load global LLM settings.")));
  }
}

async function mountLlm(userId, host) {
  host.innerHTML = "";
  const wrap = el("div", "accounts-llm-form");
  wrap.appendChild(
    el(
      "p",
      "muted",
      "Per-account custom settings override the global LLM above. Switching back to default keeps the saved custom values for later reuse.",
    ),
  );
  try {
    const data = await adminFetch(`/api/admin/users/${userId}/llm-settings`);
    const s = data.settings || {};
    const prov = el("select", "");
    prov.innerHTML =
      '<option value="default">default (server/admin)</option><option value="ollama">ollama</option><option value="openai">openai</option>';
    prov.value = String(s.mode || "default").toLowerCase() === "default" ? "default" : String(s.provider || "ollama").toLowerCase();
    const base = el("input", "");
    base.type = "text";
    base.value = String(s.base_url || "");
    const apiKey = el("input", "");
    apiKey.type = "password";
    apiKey.placeholder = "••••••• (masked)";
    apiKey.value = "";

    /** @type {HTMLInputElement | HTMLSelectElement | null} */
    let modelControl = null;
    /** @type {HTMLDivElement | null} */
    let openaiShowAllWrap = null;
    /** @type {HTMLInputElement | null} */
    let showAllModelsEl = null;

    const modelField = el("div", "field");
    const modelLabel = el("label", "", "Model");
    modelField.appendChild(modelLabel);

    async function fetchModelsList(showAll) {
      const p = prov.value.trim().toLowerCase();
      let path = `/api/models?user_id=${encodeURIComponent(String(userId))}`;
      if (p === "openai" && showAll) {
        path += "&show_all=1";
      }
      const raw = await adminFetch(path);
      return normalizeModelsListResponse(raw);
    }

    function getCurrentModelValue() {
      if (!modelControl) return String(s.model || "").trim();
      if (modelControl.tagName === "SELECT") {
        return String(/** @type {HTMLSelectElement} */ (modelControl).value || "").trim();
      }
      return String(/** @type {HTMLInputElement} */ (modelControl).value || "").trim();
    }

    /**
     * @param {string | undefined} preserveValue
     * @param {boolean | undefined} showAllToggle — when set, drives OpenAI "show all" without reading the old checkbox
     */
    async function rebuildModelControl(preserveValue, showAllToggle) {
      const useShowAll =
        typeof showAllToggle === "boolean"
          ? showAllToggle
          : !!(showAllModelsEl && showAllModelsEl.checked);

      const prev =
        preserveValue !== undefined && preserveValue !== null
          ? String(preserveValue).trim()
          : getCurrentModelValue();
      const saved = String(s.model || "").trim();
      const p = prov.value.trim().toLowerCase();

      modelControl = null;
      showAllModelsEl = null;
      openaiShowAllWrap = null;
      modelField.replaceChildren(modelLabel);

      const rowInner = el("div", "accounts-llm-model-row-inner");
      const sel = el("select", "");
      modelControl = sel;

      const refreshBtn = el("button", "secondary-btn", "Refresh models");
      refreshBtn.type = "button";
      refreshBtn.title = "Uses saved Base URL and API key. Save changes first if you edited them.";

      let models = [];
      let loadErr = null;
      try {
        models = await fetchModelsList(p === "openai" && useShowAll);
      } catch (e) {
        loadErr = parseApiError(e, "Could not load models.");
      }

      const names = new Set();
      const addOpt = (name) => {
        const n = String(name || "").trim();
        if (!n || names.has(n)) return;
        names.add(n);
        const opt = document.createElement("option");
        opt.value = n;
        opt.textContent = n;
        sel.appendChild(opt);
      };

      for (const m of models) {
        addOpt(m.name);
      }
      const want = prev || saved;
      if (want && !names.has(want)) {
        addOpt(want);
      }
      if (!names.size) {
        addOpt(want || "gemma4:e4b");
      }

      const pick =
        want && names.has(want)
          ? want
          : sel.options[0]
            ? sel.options[0].value
            : "";

      sel.value = pick;

      rowInner.appendChild(sel);
      rowInner.appendChild(refreshBtn);
      modelField.appendChild(rowInner);

      if (loadErr) {
        const hint = el("p", "muted", loadErr);
        hint.style.marginTop = "6px";
        modelField.appendChild(hint);
      }

      if (p === "openai") {
        openaiShowAllWrap = el("div", "accounts-llm-openai-models-toggle");
        const lbl = document.createElement("label");
        showAllModelsEl = /** @type {HTMLInputElement} */ (document.createElement("input"));
        showAllModelsEl.type = "checkbox";
        showAllModelsEl.checked = useShowAll;
        lbl.appendChild(showAllModelsEl);
        lbl.appendChild(document.createTextNode(" Show all provider models"));
        openaiShowAllWrap.appendChild(lbl);
        modelField.appendChild(openaiShowAllWrap);

        showAllModelsEl.addEventListener("change", async (ev) => {
          const t = /** @type {HTMLInputElement} */ (ev.target);
          await rebuildModelControl(getCurrentModelValue(), !!t.checked);
        });
      }

      refreshBtn.addEventListener("click", async () => {
        await rebuildModelControl(getCurrentModelValue(), showAllModelsEl ? !!showAllModelsEl.checked : useShowAll);
      });
    }

    function updateCustomFieldsVisibility() {
      const mode = prov.value.trim().toLowerCase();
      const showCustom = mode !== "default";
      base.parentElement.style.display = showCustom ? "" : "none";
      apiKey.parentElement.style.display = showCustom ? "" : "none";
    }

    [["Provider", prov], ["Base URL", base], ["API Key", apiKey]].forEach(([label, inp]) => {
      const f = el("div", "field");
      f.appendChild(el("label", "", String(label)));
      f.appendChild(inp);
      wrap.appendChild(f);
    });
    wrap.appendChild(modelField);

    await rebuildModelControl(String(s.model || ""));
    updateCustomFieldsVisibility();

    prov.addEventListener("change", async () => {
      updateCustomFieldsVisibility();
      await rebuildModelControl(getCurrentModelValue());
    });

    const save = el("button", "primary-btn", "Save");
    save.type = "button";
    save.addEventListener("click", async () => {
      const mode = prov.value.trim().toLowerCase() === "default" ? "default" : "custom";
      const body = {
        mode,
        provider: mode === "custom" ? prov.value.trim().toLowerCase() : "",
        base_url: mode === "custom" ? base.value.trim() : "",
        model: mode === "custom" ? getCurrentModelValue() : "",
      };
      if (mode === "custom" && apiKey.value.trim()) {
        body.api_key = apiKey.value;
      }
      try {
        await adminFetch(`/api/admin/users/${userId}/llm-settings`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
        showToast("LLM settings saved.", "success");
        apiKey.value = "";
        const dataFresh = await adminFetch(`/api/admin/users/${userId}/llm-settings`);
        Object.assign(s, dataFresh.settings || {});
        prov.value = String(s.mode || "default").toLowerCase() === "default" ? "default" : String(s.provider || "ollama").toLowerCase();
        updateCustomFieldsVisibility();
        await rebuildModelControl(body.model || String(s.model || ""));
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
      const planBtn = el("button", "secondary-btn", "🧭 GM Plan");
      planBtn.type = "button";
      planBtn.title = "T20: inspect / edit gm_plan_json and divergence";
      planBtn.addEventListener("click", () => {
        void openCampaignGmPlanModal(c.id, c.title);
      });
      td.appendChild(planBtn);
      const locBtn = el("button", "secondary-btn", "📍 Session location");
      locBtn.type = "button";
      locBtn.title = "LOC-4: view / set campaign session current_location_id";
      locBtn.addEventListener("click", () => {
        void openCampaignSessionLocationModal(c.id, c.title);
      });
      td.appendChild(locBtn);
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
