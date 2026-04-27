/**
 * Phase 8E-3 — player sheet: inventory list, gold, equip / unequip (delegated clicks).
 * Depends: window.state, window.API_BASE_URL, window.escapeHtml, window.loadInventory (this file).
 */
(function () {
  const apiBase = () => String(window.API_BASE_URL || "/api").replace(/\/+$/, "");

  window.refreshInventoryPanel = function () {
    const id = Number(window.state?.selectedCharacterId || 0);
    if (id && typeof window.loadInventory === "function") {
      void window.loadInventory(id);
    }
  };

  function occupiedSlotsFromItems(items) {
    const o = { main_hand: false, off_hand: false, armor: false };
    (items || []).forEach((it) => {
      if (Number(it.equipped) === 1 && it.slot) {
        const s = String(it.slot).toLowerCase();
        if (Object.prototype.hasOwnProperty.call(o, s)) {
          o[s] = true;
        }
      }
    });
    return o;
  }

  function pickEquipSlot(item, occupied) {
    const t = String(item.item_type || "").toLowerCase();
    if (t === "armor") return "armor";
    const key = String(item.key || "").toLowerCase();
    const lab = String(item.label || "").toLowerCase();
    if (key.includes("shield") || lab.includes("tarcz") || lab.includes("shield")) {
      return "off_hand";
    }
    if (!occupied.main_hand) return "main_hand";
    if (!occupied.off_hand) return "off_hand";
    return "main_hand";
  }

  window.loadInventory = async function (characterId) {
    const cid = Number(characterId || 0);
    if (!cid) return;

    const base = apiBase();
    let invData = { ok: false, data: [] };
    let goldGp = null;
    try {
      const [invRes, goldRes] = await Promise.all([
        fetch(`${base}/inventory/${cid}`),
        fetch(`${base}/characters/${cid}/gold`),
      ]);
      invData = await invRes.json().catch(() => ({ ok: false }));
      const goldJson = await goldRes.json().catch(() => ({}));
      if (goldJson && goldJson.ok && goldJson.data) {
        goldGp = goldJson.data.gold_gp;
      }
    } catch (_e) {
      invData = { ok: false, data: [] };
    }

    const goldEl = document.getElementById("gold-amount");
    if (goldEl && goldGp != null) {
      goldEl.textContent = String(goldGp);
    }

    const items = invData && invData.ok && Array.isArray(invData.data) ? invData.data : [];
    const occupied = occupiedSlotsFromItems(items);

    ["main_hand", "off_hand", "armor"].forEach((slot) => {
      const el = document.getElementById(`slot-${slot}`);
      if (el) el.innerHTML = "\u2014";
    });

    const backpack = document.getElementById("backpack-list");
    if (backpack) backpack.innerHTML = "";

    const esc =
      typeof window.escapeHtml === "function"
        ? window.escapeHtml
        : function (s) {
            return String(s ?? "");
          };

    items.forEach((item) => {
      const invId = item.id != null ? Number(item.id) : null;
      if (invId == null || !Number.isFinite(invId)) return;

      if (Number(item.equipped) === 1 && item.slot) {
        const slotEl = document.getElementById(`slot-${String(item.slot).toLowerCase()}`);
        if (slotEl) {
          const name = esc(item.label || item.key || "?");
          slotEl.innerHTML = `<span class="slot-item-name">${name}</span><button type="button" class="btn-unequip" data-inventory-id="${invId}">Zdejmij</button>`;
        }
      } else if (backpack) {
        const li = document.createElement("li");
        li.className = "backpack-item";
        const t = String(item.item_type || "").toLowerCase();
        const canEquip = t === "weapon" || t === "armor";
        const name = esc(item.label || item.key || "?");
        const qty = Number(item.quantity) > 1 ? `<span class="item-qty">\u00d7${esc(item.quantity)}</span>` : "";
        const equipBtn = canEquip
          ? `<button type="button" class="btn-equip" data-inventory-id="${invId}" data-item-type="${esc(t)}">Za\u0142\u00f3\u017c</button>`
          : "";
        li.innerHTML = `<span class="item-name">${name}</span>${qty}${equipBtn}`;
        backpack.appendChild(li);
      }
    });

    const narrativeSection = document.getElementById("narrative-items-section");
    const narrativeList = document.getElementById("narrative-items-list");
    if (narrativeSection && narrativeList) {
      const narrativeItems = Array.isArray(window.state?.characterSheet?.narrative_items)
        ? window.state.characterSheet.narrative_items
        : [];
      narrativeList.innerHTML = "";
      if (narrativeItems.length > 0) {
        narrativeItems.forEach((item) => {
          if (!item || typeof item !== "object") return;
          const li = document.createElement("li");
          li.className = "narrative-item";
          const label = esc(item.label || "Przedmiot");
          const desc = item.description
            ? `<span class="narrative-item-desc">${esc(item.description)}</span>`
            : "";
          li.innerHTML = `<span class="narrative-item-label">${label}</span>${desc}`;
          narrativeList.appendChild(li);
        });
        narrativeSection.classList.remove("hidden");
      } else {
        narrativeSection.classList.add("hidden");
      }
    }
  };

  if (window.__inventoryEquipDelegationWired) return;
  window.__inventoryEquipDelegationWired = true;

  document.addEventListener("click", async (e) => {
    const equipBtn = e.target.closest(".btn-equip");
    const unequipBtn = e.target.closest(".btn-unequip");
    if (!equipBtn && !unequipBtn) return;

    const cid = Number(window.state?.selectedCharacterId || 0);
    if (!cid) return;

    const base = apiBase();

    if (equipBtn) {
      e.preventDefault();
      const inventoryId = Number(equipBtn.getAttribute("data-inventory-id"));
      if (!Number.isFinite(inventoryId)) return;

      let invList = [];
      try {
        const invRes = await fetch(`${base}/inventory/${cid}`);
        const invJson = await invRes.json();
        if (invJson && invJson.ok && Array.isArray(invJson.data)) {
          invList = invJson.data;
        }
      } catch (_err) {
        return;
      }

      const row = invList.find((x) => Number(x.id) === inventoryId);
      if (!row) return;
      const occupied = occupiedSlotsFromItems(invList);
      const slot = pickEquipSlot(row, occupied);

      try {
        const res = await fetch(`${base}/inventory/${cid}/equip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ inventory_id: inventoryId, slot }),
        });
        if (!res.ok) return;
      } catch (_err) {
        return;
      }
      void window.loadInventory(cid);
      return;
    }

    if (unequipBtn) {
      e.preventDefault();
      const inventoryId = Number(unequipBtn.getAttribute("data-inventory-id"));
      if (!Number.isFinite(inventoryId)) return;
      try {
        const res = await fetch(`${base}/inventory/${cid}/equip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ inventory_id: inventoryId, slot: null }),
        });
        if (!res.ok) return;
      } catch (_err) {
        return;
      }
      void window.loadInventory(cid);
    }
  });
})();
