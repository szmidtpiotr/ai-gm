(function () {
  const apiBase = () => String(window.API_BASE_URL || "/api").replace(/\/+$/, "");

  function esc(s) {
    return typeof window.escapeHtml === "function" ? window.escapeHtml(s) : String(s ?? "");
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function getState() {
    return window.state || {};
  }

  function closeModal() {
    const modal = byId("shop-modal");
    if (!modal) return;
    modal.style.display = "none";
    modal.setAttribute("aria-hidden", "true");
    modal.hidden = true;
    modal.classList.add("hidden");
  }

  function openModal() {
    const modal = byId("shop-modal");
    if (!modal) return;
    modal.hidden = false;
    modal.classList.remove("hidden");
    // Same pattern as campaign/history overlays: `.character-modal-overlay { display: none }` in CSS
    modal.style.display = "flex";
    modal.setAttribute("aria-hidden", "false");
  }

  function toast(msg) {
    if (typeof window.addMessage === "function") {
      window.addMessage({ speaker: "System", text: `🏪 ${msg}`, role: "system" });
    }
  }

  async function fetchShopDataByKey(npcKey, characterId) {
    const resp = await fetch(
      `${apiBase()}/shop/by-key/${encodeURIComponent(String(npcKey))}?character_id=${encodeURIComponent(
        String(characterId)
      )}`
    );
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) {
      const detail = data?.detail || `HTTP ${resp.status}`;
      throw new Error(String(detail));
    }
    return data.data || {};
  }

  async function postBuy(npcId, characterId, itemType, itemKey) {
    const resp = await fetch(`${apiBase()}/shop/${encodeURIComponent(String(npcId))}/buy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ character_id: characterId, item_type: itemType, item_key: itemKey }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) {
      const detail = data?.detail || `HTTP ${resp.status}`;
      throw new Error(String(detail));
    }
    return data.data || {};
  }

  async function postSell(npcId, characterId, inventoryId) {
    const resp = await fetch(`${apiBase()}/shop/${encodeURIComponent(String(npcId))}/sell`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ character_id: characterId, inventory_id: inventoryId }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) {
      const detail = data?.detail || `HTTP ${resp.status}`;
      throw new Error(String(detail));
    }
    return data.data || {};
  }

  function setGold(v) {
    const el = byId("shop-gold");
    if (el) el.textContent = String(v ?? 0);
  }

  function renderShop(data, characterId) {
    const titleEl = byId("shop-title");
    const buyList = byId("shop-buy-list");
    const sellList = byId("shop-sell-list");
    if (!titleEl || !buyList || !sellList) return;

    titleEl.textContent = `🏪 Sklep — ${data?.npc?.label || "NPC"}`;
    setGold(data?.character_gold ?? 0);
    buyList.innerHTML = "";
    sellList.innerHTML = "";

    const items = Array.isArray(data?.items) ? data.items : [];
    if (!items.length) {
      buyList.innerHTML = '<li class="muted">Brak asortymentu.</li>';
    } else {
      items.forEach((it) => {
        const li = document.createElement("li");
        li.className = "shop-row";
        li.innerHTML = `
          <div class="shop-row-main">
            <strong>${esc(it.label || it.key)}</strong>
            <span class="muted">(${esc(it.type)})</span>
            <span>— ${esc(it.value_gp)} GP</span>
          </div>
          <button type="button" class="secondary">Kup</button>
        `;
        const btn = li.querySelector("button");
        btn.addEventListener("click", async () => {
          btn.disabled = true;
          try {
            await postBuy(data.npc.id, characterId, String(it.type || "item"), String(it.key || ""));
            const fresh = await fetchShopDataByKey(data.npc.key, characterId);
            renderShop(fresh, characterId);
            if (typeof window.loadInventory === "function") {
              void window.loadInventory(characterId);
            }
            toast(`Kupiono: ${it.label || it.key}`);
          } catch (e) {
            toast(e.message || "Zakup nieudany");
          } finally {
            btn.disabled = false;
          }
        });
        buyList.appendChild(li);
      });
    }

    const sellItems = Array.isArray(data?.sell_items) ? data.sell_items : [];
    if (!sellItems.length) {
      sellList.innerHTML = '<li class="muted">Brak przedmiotów do sprzedaży.</li>';
    } else {
      sellItems.forEach((it) => {
        const li = document.createElement("li");
        li.className = "shop-row";
        const qty = Number(it.quantity || 1) > 1 ? ` x${it.quantity}` : "";
        li.innerHTML = `
          <div class="shop-row-main">
            <strong>${esc(it.label || it.key)}${esc(qty)}</strong>
            <span class="muted">(${esc(it.item_type)})</span>
            <span>— ${esc(it.sell_price_gp)} GP</span>
          </div>
          <button type="button" class="secondary">Sprzedaj</button>
        `;
        const btn = li.querySelector("button");
        btn.addEventListener("click", async () => {
          btn.disabled = true;
          try {
            await postSell(data.npc.id, characterId, Number(it.inventory_id));
            const fresh = await fetchShopDataByKey(data.npc.key, characterId);
            renderShop(fresh, characterId);
            if (typeof window.loadInventory === "function") {
              void window.loadInventory(characterId);
            }
            toast(`Sprzedano: ${it.label || it.key}`);
          } catch (e) {
            toast(e.message || "Sprzedaż nieudana");
          } finally {
            btn.disabled = false;
          }
        });
        sellList.appendChild(li);
      });
    }
  }

  window.openShopByNpcKey = async function (npcKey, characterId) {
    const cid = Number(characterId || getState().selectedCharacterId || 0);
    if (!cid) {
      toast("Wybierz postać na karcie (brak wybranego character_id) — nie można otworzyć sklepu.");
      try {
        console.warn("openShopByNpcKey: missing character id", {
          npcKey,
          selectedCharacterId: getState().selectedCharacterId,
        });
      } catch (_e) {
        /* ignore */
      }
      return;
    }
    if (!npcKey) {
      toast("Brak identyfikatora kupca (npc_key).");
      return;
    }
    try {
      const data = await fetchShopDataByKey(String(npcKey), cid);
      renderShop(data, cid);
      openModal();
    } catch (e) {
      toast(e.message || "Nie udało się otworzyć sklepu.");
    }
  };

  document.addEventListener("DOMContentLoaded", () => {
    const closeBtn = byId("shop-close-btn");
    const modal = byId("shop-modal");
    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (modal) {
      modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModal();
      });
    }
  });
})();
