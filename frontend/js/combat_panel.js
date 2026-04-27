/**
 * Phase 8B — combat UI (solo). Uses /api/campaigns/:id/combat/* endpoints.
 */
(function () {
  const esc = (s) => (window.escapeHtml ? window.escapeHtml(String(s ?? "")) : String(s ?? ""));

  function hpTier(pct) {
    if (pct > 50) return "high";
    if (pct > 25) return "mid";
    return "low";
  }

  function lootIcon(entry) {
    const t = String(entry?.source_type || entry?.item_type || "");
    if (t === "weapon") return "⚔️";
    if (t === "consumable") return "🧪";
    return "📦";
  }

  function lootLabel(entry) {
    const k = String(entry?.label || entry?.source_key || entry?.key || "?");
    return k.replace(/_/g, " ");
  }

  function lootQty(entry) {
    const n = Number(entry?.qty ?? entry?.quantity ?? 1);
    return Number.isFinite(n) && n > 0 ? n : 1;
  }

  class CombatPanel {
    constructor() {
      this._state = null;
      this._accumulatedLoot = [];
      /** Loot from killing blow — applied after GM SSE narration (victory). */
      this._pendingLoot = null;
      /** Gold reward from killing blow (8E-4). */
      this._pendingGold = 0;
      /** When true, victory overlay is deferred until `showVictoryAfterNarration`. */
      this._deferVictoryOverlay = false;
      this._busy = false;
      this._host = null;
      this._card = null;
      this._bodyEl = null;
      this._actionsEl = null;
      this._msgEl = null;
      this._enemyOverlay = null;
      /** @type {ReturnType<typeof setTimeout>|null} */
      this._enemyOverlayHideTimer = null;
      /** @type {Map<string, ReturnType<typeof setTimeout>>} */
      this._flashTimers = new Map();
      this._lootLayer = null;
      this._endLayer = null;
    }

    _campaignId() {
      return window.state?.selectedCampaignId ? Number(window.state.selectedCampaignId) : null;
    }

    ensureDom() {
      const slot = document.getElementById("combat-panel-slot");
      if (!slot) return;

      this._host = document.getElementById("combat-panel-host");
      if (!this._host) {
        this._host = document.createElement("div");
        this._host.id = "combat-panel-host";
        this._host.className = "combat-panel-host combat-panel-host--hidden";
        this._host.setAttribute("aria-live", "polite");
        slot.appendChild(this._host);
      } else if (!slot.contains(this._host)) {
        slot.appendChild(this._host);
      }

      if (this._card) return;

      this._host.innerHTML = `
        <div class="combat-panel-card" hidden>
          <div class="combat-panel-header">
            <h2 class="combat-panel-title">Walka</h2>
            <span class="combat-panel-meta" id="combat-panel-meta"></span>
          </div>
          <div class="combat-engine-turns" id="combat-engine-turns" hidden></div>
          <div class="combat-panel-body" id="combat-panel-body"></div>
          <div class="combat-msg" id="combat-panel-msg" style="display:none;"></div>
          <div class="combat-actions" id="combat-panel-actions">
            <button type="button" class="combat-btn combat-btn--attack" id="combat-btn-attack">Atak</button>
            <button type="button" class="combat-btn combat-btn--flee" id="combat-btn-flee">Ucieczka</button>
            <button type="button" class="combat-btn combat-btn--item" id="combat-btn-item" disabled>Przedmiot</button>
          </div>
          <div class="combat-enemy-turn-overlay" id="combat-enemy-overlay" style="display:none;" aria-hidden="true">
            <span class="combat-enemy-turn-label">ENEMY TURN</span>
          </div>
        </div>
      `;

      this._card = this._host.querySelector(".combat-panel-card");
      this._bodyEl = this._host.querySelector("#combat-panel-body");
      this._msgEl = this._host.querySelector("#combat-panel-msg");
      this._actionsEl = this._host.querySelector("#combat-panel-actions");
      this._enemyOverlay = this._host.querySelector("#combat-enemy-overlay");

      const loot = document.createElement("div");
      loot.id = "combat-loot-layer";
      loot.className = "combat-loot-modal";
      loot.style.display = "none";
      loot.setAttribute("aria-hidden", "true");
      document.body.appendChild(loot);
      this._lootLayer = loot;

      const end = document.createElement("div");
      end.id = "combat-end-layer";
      end.className = "combat-end-screen";
      end.style.display = "none";
      end.setAttribute("aria-hidden", "true");
      document.body.appendChild(end);
      this._endLayer = end;

      this._host.querySelector("#combat-btn-attack").onclick = () => this._onAttack();
      this._host.querySelector("#combat-btn-flee").onclick = () => this._onFlee();
    }

    _showEnemyOverlay() {
      const el = this._enemyOverlay;
      if (!el) return;
      if (this._enemyOverlayHideTimer != null) {
        clearTimeout(this._enemyOverlayHideTimer);
        this._enemyOverlayHideTimer = null;
      }
      el.classList.remove("combat-enemy-overlay--fade-out");
      el.classList.remove("combat-enemy-overlay--fade-in");
      el.style.display = "flex";
      el.setAttribute("aria-hidden", "false");
      void el.offsetWidth;
      el.classList.add("combat-enemy-overlay--fade-in");
    }

    _hideEnemyOverlay() {
      const el = this._enemyOverlay;
      if (!el) return;
      const disp = String(el.style.display || "");
      if (
        (disp === "none" || disp === "") &&
        !el.classList.contains("combat-enemy-overlay--fade-out") &&
        !el.classList.contains("combat-enemy-overlay--fade-in")
      ) {
        el.setAttribute("aria-hidden", "true");
        return;
      }
      if (this._enemyOverlayHideTimer != null) {
        clearTimeout(this._enemyOverlayHideTimer);
        this._enemyOverlayHideTimer = null;
      }
      el.classList.remove("combat-enemy-overlay--fade-in");
      el.classList.add("combat-enemy-overlay--fade-out");
      el.setAttribute("aria-hidden", "true");
      this._enemyOverlayHideTimer = setTimeout(() => {
        this._enemyOverlayHideTimer = null;
        el.classList.remove("combat-enemy-overlay--fade-out");
        el.style.display = "none";
      }, 300);
    }

    _flashElement(el, cls, ms) {
      if (!el) return;
      const prev = this._flashTimers.get(cls);
      if (prev != null) clearTimeout(prev);
      el.classList.remove(cls);
      void el.offsetWidth;
      el.classList.add(cls);
      const t = setTimeout(() => {
        this._flashTimers.delete(cls);
        el.classList.remove(cls);
      }, ms);
      this._flashTimers.set(cls, t);
    }

    show() {
      this.ensureDom();
      if (!this._host || !this._card) return;
      this._host.classList.remove("combat-panel-host--hidden");
      this._card.hidden = false;
    }

    /** Victory / end-of-combat UI (combat_state.status === "ended"). */
    showVictory(combatState) {
      this.ensureDom();
      if (!combatState) return;
      this._state = combatState;
      this.show();
      this.render(combatState);
    }

    /**
     * After combat-kill SSE narration: optional loot modal, then merge into accumulated list and victory UI.
     * @param {object|null} _killedData payload from [COMBAT_ENDED] (optional; victory uses `this._state`)
     */
    async showVictoryAfterNarration(_killedData) {
      this._deferVictoryOverlay = false;
      const pending = Array.isArray(this._pendingLoot) ? this._pendingLoot.slice() : [];
      const pendingGold = Math.max(0, Number(this._pendingGold || 0));
      this._pendingLoot = null;
      this._pendingGold = 0;
      const fromState = Array.isArray(this._state?.loot_pool) ? this._state.loot_pool.slice() : [];
      const drop = pending.length > 0 ? pending : fromState;
      if (drop.length > 0 || pendingGold > 0) {
        const claimed = await this._showLootPopupAsync(drop, pendingGold);
        this._pushLoot(Array.isArray(claimed) ? claimed : []);
        await this._runPostLootNarration(
          Array.isArray(claimed) ? claimed.length : 0,
          drop.length
        );
      }
      if (typeof window.refreshInventoryPanel === "function") {
        window.refreshInventoryPanel();
      }
      if (this._state) {
        this.showVictory(this._state);
      }
    }

    cancelDeferredVictoryUi() {
      this._deferVictoryOverlay = false;
      this._pendingLoot = null;
      this._pendingGold = 0;
      this._hideLoot();
      this._hideEnd();
    }

    _playerAttackRollDbLine(intent, characterName, d20, mod, total, data, combatVictory) {
      const hit = !!data.hit;
      const dmg = data.damage != null ? Number(data.damage) : null;
      const summary = hit
        ? `Atakuję z wynikiem ${total} — trafiam za ${dmg != null ? dmg : "?"} obrażeń!`
        : (data.player_nat1
            ? `Atakuję z wynikiem ${total} — fatalnie pudłuję i tracę tempo ataku!`
            : (data.dodged
            ? `Atakuję z wynikiem ${total} — przeciwnik uskakuje i unika ciosu!`
            : `Atakuję z wynikiem ${total} — pudło!`));
      const tac =
        data.target_ac != null && Number.isFinite(Number(data.target_ac))
          ? Number(data.target_ac)
          : null;
      const payload = {
        kind: "player_attack",
        intent: (intent || "").trim(),
        summary_line: summary,
        character_name: characterName,
        attack_label: "ATAK (STR)",
        d20,
        modifiers: [{ name: "STR", value: mod }],
        total,
        hit,
        damage: dmg != null ? dmg : 0,
        enemy_key: data.enemy_key != null ? String(data.enemy_key) : "",
        target_id: data.target_id != null ? String(data.target_id) : "",
        target_name:
          data.target_name != null ? String(data.target_name) : "",
        target_ac: tac,
        dodged: !!data.dodged,
        player_nat1: !!data.player_nat1,
        enemy_dead: !!data.enemy_dead,
        combat_victory: !!combatVictory,
      };
      return `${window.COMBAT_ROLL_PREFIX}\n${JSON.stringify(payload)}`;
    }

    /**
     * Jedyny punkt wejścia narracji GM (SSE) po akcjach walki: atak i ucieczka.
     * Nie wywołuj `window.triggerCombatNarration` ani `sendMessage` z panelu poza tą metodą.
     */
    async _sendCombatNarrativeFollowUp(dbUserLine) {
      if (typeof window.triggerCombatNarration === "function") {
        await window.triggerCombatNarration(dbUserLine);
        return;
      }
      if (typeof window.sendMessage !== "function") return;
      const { inputEl } = window.getEls ? window.getEls() : {};
      if (inputEl) inputEl.value = "";
      window.__pendingNarrativeUserTextForApi = dbUserLine;
      window.__suppressNextUserBubbleForGm = true;
      await window.sendMessage();
    }

    /** Wpis w czacie (JSON rzutu) przed strumieniem GM — tylko z `_onAttack`. */
    _appendCombatAttackRollUserChatLine(dbLine, charName, turnNum) {
      if (typeof window.addMessage === "function") {
        window.addMessage({
          speaker: charName,
          text: dbLine,
          role: "user",
          route: "input",
          turn: turnNum,
          createdAt: new Date().toISOString(),
        });
      }
      const { inputEl } = window.getEls ? window.getEls() : {};
      if (inputEl) inputEl.value = "";
    }

    /**
     * Nazwa aktualnego / głównego wroga przed ucieczką (snapshot stanu walki).
     */
    _fleeEnemyDisplayName(combatState) {
      if (!combatState || !Array.isArray(combatState.combatants)) {
        return "przeciwnik";
      }
      const cur = String(combatState.current_turn || "");
      const byId = {};
      combatState.combatants.forEach((c) => {
        if (c && c.id != null) byId[String(c.id)] = c;
      });
      if (cur && cur !== "player" && byId[cur] && byId[cur].type === "enemy") {
        return String(byId[cur].name || byId[cur].enemy_key || "przeciwnik");
      }
      const living = combatState.combatants.filter(
        (c) => c && c.type === "enemy" && Number(c.hp_current ?? 0) > 0
      );
      if (living.length === 1) {
        return String(living[0].name || living[0].enemy_key || "przeciwnik");
      }
      if (living.length > 1) {
        const names = living
          .map((e) => e.name || e.enemy_key)
          .filter(Boolean);
        return names.length ? names.join(", ") : "przeciwnicy";
      }
      return "przeciwnik";
    }

    _playerFleeDbLine(intent, characterName, enemyName) {
      const en = (enemyName || "przeciwnik").trim() || "przeciwnik";
      const summary = `Udało mi się wyrwać z walki z ${en} (silnik) — proszę o domknięcie sceny: chaos, reakcja wrogów, gdzie jestem teraz.`;
      const payload = {
        kind: "player_flee",
        intent: (intent || "").trim(),
        summary_line: summary,
        character_name: characterName,
        enemy_name: en,
        success: true,
      };
      return `${window.COMBAT_ROLL_PREFIX}\n${JSON.stringify(payload)}`;
    }

    hide() {
      if (this._host) this._host.classList.add("combat-panel-host--hidden");
      if (this._card) this._card.hidden = true;
      this._hideLoot();
      this._hideEnd();
    }

    _setMsg(text, isError) {
      if (!this._msgEl) return;
      if (!text) {
        this._msgEl.style.display = "none";
        this._msgEl.textContent = "";
        this._msgEl.classList.remove("combat-msg--error");
        return;
      }
      this._msgEl.style.display = "block";
      this._msgEl.textContent = text;
      this._msgEl.classList.toggle("combat-msg--error", !!isError);
    }

    render(combatState) {
      this.ensureDom();
      if (!this._bodyEl || !this._card) return;
      this._state = combatState || null;

      const st = combatState;
      if (!st) {
        this._bodyEl.innerHTML = "";
        const turnsEl = this._host?.querySelector("#combat-engine-turns");
        if (turnsEl) {
          turnsEl.innerHTML = "";
          turnsEl.hidden = true;
        }
        if (this._enemyOverlay) {
          if (this._enemyOverlayHideTimer != null) {
            clearTimeout(this._enemyOverlayHideTimer);
            this._enemyOverlayHideTimer = null;
          }
          this._enemyOverlay.classList.remove(
            "combat-enemy-overlay--fade-in",
            "combat-enemy-overlay--fade-out"
          );
          this._enemyOverlay.style.display = "none";
          this._enemyOverlay.setAttribute("aria-hidden", "true");
        }
        return;
      }

      this._syncCombatDebugEnemyHintFromState(st);

      const round = Number(st.round || 1);
      const cur = String(st.current_turn || "");
      const combatants = Array.isArray(st.combatants) ? st.combatants : [];

      const nameById = {};
      combatants.forEach((c) => {
        if (c && c.id != null) nameById[String(c.id)] = c.name || c.id;
      });
      const curLabel = cur === "player" ? "Gracz" : String(nameById[cur] || cur || "—");

      const meta = this._host.querySelector("#combat-panel-meta");
      if (meta) {
        meta.textContent = `Runda ${round} · Tura: ${curLabel}`;
      }

      const rowHtml = (c, isPlayer) => {
        const hp = Number(c.hp_current ?? 0);
        const max = Math.max(1, Number(c.hp_max ?? 1));
        const pct = Math.max(0, Math.min(100, (hp / max) * 100));
        const tier = hpTier(pct);
        const conds = Array.isArray(c.conditions) ? c.conditions.filter(Boolean) : [];
        const condHtml =
          conds.length > 0
            ? `<div class="combat-conditions">${conds
                .map((x) => `<span class="combat-condition-badge">${esc(x)}</span>`)
                .join("")}</div>`
            : "";
        return `
            <div class="combat-combatant" data-cid="${esc(c.id)}">
              <div class="combat-combatant-name">
                <span>${esc(c.name || (isPlayer ? "Bohater" : c.id))}</span>
                <span class="muted" style="font-size:11px;">INI ${esc(c.initiative_roll ?? "—")}</span>
              </div>
              <div class="combat-hp-row"><span>HP</span><span>${hp} / ${max} · DEF ${esc(c.defense ?? "—")}</span></div>
              <div class="combat-hp-bar"><div class="combat-hp-fill combat-hp-fill--${tier}" style="width:${pct.toFixed(
                0
              )}%"></div></div>
              ${condHtml}
            </div>
          `;
      };

      const parts = [];
      const player = combatants.find((x) => x && x.type === "player");
      if (player) parts.push(rowHtml(player, true));

      combatants.forEach((c) => {
        if (!c || c.type !== "enemy") return;
        if (Number(c.hp_current ?? 0) <= 0) return;
        parts.push(rowHtml(c, false));
      });

      this._bodyEl.innerHTML = parts.join("") || '<p class="muted">Brak danych walki.</p>';

      const active = String(st.status || "") === "active";
      const playerTurn = cur === "player";
      const atk = this._host.querySelector("#combat-btn-attack");
      const flee = this._host.querySelector("#combat-btn-flee");
      if (atk) atk.disabled = this._busy || !active || !playerTurn;
      if (flee) flee.disabled = this._busy || !active || !playerTurn;
      const panelActions = this._host.querySelector("#combat-panel-actions");
      if (panelActions) {
        panelActions.style.display = "none";
      }

      if (this._enemyOverlay) {
        const showEnemy = active && cur !== "player" && cur.length > 0;
        if (showEnemy) {
          this._showEnemyOverlay();
        } else {
          this._hideEnemyOverlay();
        }
      }

      const ended = String(st.status || "") === "ended";
      if (ended && !this._deferVictoryOverlay) {
        this._showEndScreen(st);
      } else {
        this._hideEnd();
      }

      void this._refreshCombatEngineTurnsPanel();
    }

    _showEndScreen(st) {
      const reason = String(st.ended_reason || "");
      if (!this._endLayer) return;
      if (reason === "victory") {
        const items = this._accumulatedLoot.length
          ? this._accumulatedLoot
              .map(
                (L) =>
                  `<li class="combat-loot-row"><span class="combat-loot-icon">${lootIcon(L)}</span><span>${esc(
                    lootLabel(L)
                  )}</span><span class="combat-loot-qty">×${esc(lootQty(L))}</span></li>`
              )
              .join("")
          : '<li class="muted">Brak łupów.</li>';
        this._endLayer.innerHTML = `
          <div class="combat-end-inner combat-end-inner--victory">
            <h3 class="combat-end-title">Zwycięstwo! Wszyscy wrogowie pokonani.</h3>
            <p class="muted" style="margin-top:0;">Łupy z walki:</p>
            <ul class="combat-loot-list">${items}</ul>
            <button type="button" class="combat-primary-btn" id="combat-end-continue-v">Kontynuuj</button>
          </div>`;
        this._endLayer.style.display = "flex";
        this._endLayer.querySelector("#combat-end-continue-v").onclick = () => this._finishEndOverlay();
      } else if (reason === "fled") {
        this._endLayer.innerHTML = `
          <div class="combat-end-inner combat-end-inner--fled">
            <h3 class="combat-end-title">Udało ci się uciec!</h3>
            <button type="button" class="combat-primary-btn" id="combat-end-continue-f">Kontynuuj</button>
          </div>`;
        this._endLayer.style.display = "flex";
        this._endLayer.querySelector("#combat-end-continue-f").onclick = () => this._finishEndOverlay();
      } else if (reason === "player_dead") {
        this._triggerDeathSavePrompt();
        this._endLayer.innerHTML = `
          <div class="combat-end-inner combat-end-inner--defeat">
            <h3 class="combat-end-title">Zostałeś pokonany…</h3>
            <button type="button" class="combat-primary-btn secondary" id="combat-end-continue-d">Kontynuuj</button>
          </div>`;
        this._endLayer.style.display = "flex";
        this._endLayer.querySelector("#combat-end-continue-d").onclick = () => this._finishEndOverlay();
      } else {
        this._hideEnd();
      }
    }

    _finishEndOverlay() {
      this._hideEnd();
      this._accumulatedLoot = [];
      this.hide();
      this._state = null;
    }

    _hideEnd() {
      if (this._endLayer) {
        this._endLayer.style.display = "none";
        this._endLayer.innerHTML = "";
      }
    }

    _hideLoot() {
      if (this._lootLayer) {
        this._lootLayer.style.display = "none";
        this._lootLayer.innerHTML = "";
      }
    }

    async _claimLootSelection(lootArr, selectedIndexes) {
      const cid = this._campaignId();
      const characterId = Number(window.state?.selectedCharacterId || 0);
      if (!cid || !characterId || !Array.isArray(lootArr)) return [];
      try {
        const resp = await fetch(`/api/campaigns/${cid}/combat/loot/claim`, {
          method: "POST",
          headers: window.getApiHeaders ? window.getApiHeaders() : { "Content-Type": "application/json" },
          body: JSON.stringify({
            character_id: characterId,
            selected_indexes: Array.isArray(selectedIndexes) ? selectedIndexes : [],
          }),
        });
        const payload = await resp.json().catch(() => ({}));
        if (!resp.ok || !payload?.ok) return [];
        const claimed = payload?.data?.claimed;
        return Array.isArray(claimed) ? claimed : [];
      } catch (_err) {
        return [];
      }
    }

    _showLootPopup(lootArr, goldDrop, onDismiss) {
      if (!this._lootLayer) return;
      const list = Array.isArray(lootArr) ? lootArr : [];
      const gold = Math.max(0, Number(goldDrop || 0));
      const inner =
        list.length === 0
          ? '<p class="muted">Wróg nie miał łupów.</p>'
          : `<ul class="combat-loot-list">${list
              .map((L, idx) =>
                  `<li class="combat-loot-row"><label style="display:flex;align-items:center;gap:8px;width:100%;"><input type="checkbox" data-loot-pick="${idx}" checked /><span class="combat-loot-icon">${lootIcon(L)}</span><span>${esc(
                    lootLabel(L)
                  )}</span><span class="combat-loot-qty">×${esc(lootQty(L))}</span></label></li>`
              )
              .join("")}</ul>`;
      this._lootLayer.innerHTML = `
        <div class="combat-loot-inner">
          <h3 style="margin:0 0 10px;font-size:16px;">Łupy z pokonanych</h3>
          ${inner}
          ${gold > 0 ? `<div class="combat-loot-gold">💰 +${esc(gold)} GP</div>` : ""}
          <button type="button" class="combat-primary-btn" id="combat-loot-claim">Weź wybrane</button>
          <button type="button" class="combat-primary-btn secondary" id="combat-loot-dismiss">Pomiń</button>
        </div>`;
      this._lootLayer.style.display = "flex";
      this._lootLayer.querySelector("#combat-loot-claim").onclick = async () => {
        const picks = Array.from(this._lootLayer.querySelectorAll("[data-loot-pick]:checked"))
          .map((x) => Number(x.getAttribute("data-loot-pick")))
          .filter((n) => Number.isInteger(n) && n >= 0);
        const claimed = await this._claimLootSelection(list, picks);
        this._hideLoot();
        if (typeof onDismiss === "function") onDismiss(claimed);
      };
      this._lootLayer.querySelector("#combat-loot-dismiss").onclick = async () => {
        const claimed = await this._claimLootSelection(list, []);
        this._hideLoot();
        if (typeof onDismiss === "function") onDismiss(claimed);
      };
    }

    _showLootPopupAsync(lootArr, goldDrop = 0) {
      return new Promise((resolve) => {
        this._showLootPopup(lootArr, goldDrop, (claimed) => resolve(claimed));
      });
    }

    async _runPostLootNarration(claimedCount, totalCount) {
      const total = Math.max(0, Number(totalCount || 0));
      if (!total) return;
      const claimed = Math.max(0, Number(claimedCount || 0));
      const line =
        claimed > 0
          ? `Po walce wybieram ${claimed} z ${total} elementów łupu i rozglądam się po okolicy.`
          : "Po walce rezygnuję z łupów i rozglądam się po okolicy.";
      await this._sendCombatNarrativeFollowUp(line);
    }

    _triggerDeathSavePrompt() {
      if (typeof window.updateActionTriggerBtn !== "function") return;
      const hp =
        typeof window.getCharacterHpForRollRules === "function"
          ? window.getCharacterHpForRollRules()
          : null;
      if (hp === null || hp > 0) return;
      window.state.activeRollRequest = {
        skill: "death_save",
        dice: "d20",
        description:
          (typeof window.getTestDescription === "function" && window.getTestDescription("death_save")) ||
          "Rzut obronny przed śmiercią.",
      };
      window.updateActionTriggerBtn(true);
    }

    _pushLoot(loot) {
      if (!Array.isArray(loot) || loot.length === 0) return;
      loot.forEach((x) => {
        if (x) this._accumulatedLoot.push(x);
      });
    }

    async fetchAndMaybeShow() {
      const cid = this._campaignId();
      if (!cid) return;
      try {
        const resp = await fetch(`/api/campaigns/${cid}/combat`);
        if (!resp.ok) return;
        const cd = await resp.json().catch(() => ({}));
        if (typeof window.updateCombatDebugStatusLabel === "function") {
          window.updateCombatDebugStatusLabel(cd);
        }
        if (!cd.active || !cd.combat) {
          this._state = null;
          this.hide();
          return;
        }
        const data = cd.combat;
        if (String(data.status) === "active") {
          this.show();
          this.render(data);
        } else {
          this.hide();
        }
      } catch (_e) {
        /* ignore */
      }
    }

    applyCombatInitiated(combatState) {
      if (!combatState) return;
      this._accumulatedLoot = [];
      this._pendingLoot = null;
      this._pendingGold = 0;
      this._deferVictoryOverlay = false;
      if (typeof window !== "undefined" && window.state) {
        window.state._combatVictoryUiPending = false;
      }
      this.render(combatState);
      this.show();
    }

    async _onFlee() {
      const cid = this._campaignId();
      if (!cid || this._busy) return;
      this._busy = true;
      this._setMsg("");
      const { inputEl } = window.getEls ? window.getEls() : {};
      const intentRaw = inputEl ? String(inputEl.value || "").trim() : "";
      try {
        if (intentRaw && typeof window.addMessage === "function") {
          const tn = typeof window.nextTurnNumber === "function" ? window.nextTurnNumber() : null;
          const nm =
            typeof window.currentCharacterName === "function"
              ? window.currentCharacterName()
              : "Gracz";
          window.addMessage({
            speaker: nm,
            text: `${intentRaw}\n\n— Próbuję uciec z walki!`,
            role: "user",
            route: "input",
            turn: tn,
            createdAt: new Date().toISOString(),
          });
          inputEl.value = "";
        }
        const resp = await fetch(`/api/campaigns/${cid}/combat/flee`, {
          method: "POST",
          headers: window.getApiHeaders ? window.getApiHeaders() : { "Content-Type": "application/json" },
        });
        const fleeData = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          const detail = fleeData.detail || fleeData.message || `HTTP ${resp.status}`;
          throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
        }
        const combatSnap = this._state;
        const enemyLabel = this._fleeEnemyDisplayName(combatSnap);

        this.hide();
        if (typeof window.combatInput?.syncWithCombat === "function") {
          window.combatInput.syncWithCombat(null);
        }
        this._accumulatedLoot = [];
        this._state = null;

        if (!fleeData.already_ended) {
          const nm =
            typeof window.currentCharacterName === "function"
              ? window.currentCharacterName()
              : "Gracz";
          const dbLine = this._playerFleeDbLine(intentRaw, nm, enemyLabel);
          await this._sendCombatNarrativeFollowUp(dbLine);
        }
      } catch (e) {
        this._setMsg(e.message || "Ucieczka nie powiodła się.", true);
      } finally {
        this._busy = false;
      }
    }

    /**
     * Cel ataku gracza wg kolejki inicjatywy i żywych wrogów (zgodnie z silnikiem na backendzie).
     * @returns {({ target_id: string, enemy_key: string, target_name: string })|null}
     */
    _currentPlayerAttackTarget() {
      const cs = this._state;
      if (!cs || String(cs.status) !== "active" || cs.current_turn !== "player") return null;
      const combatants = Array.isArray(cs.combatants) ? cs.combatants : [];
      const living = combatants.filter(
        (c) => c && c.type === "enemy" && Number(c.hp_current ?? 0) > 0
      );
      if (!living.length) return null;
      const order = Array.isArray(cs.turn_order) ? cs.turn_order : [];
      const livingSet = new Set(living.map((e) => String(e.id)));
      let tid = null;
      for (const id of order) {
        if (livingSet.has(String(id))) {
          tid = String(id);
          break;
        }
      }
      if (!tid) tid = String(living[0].id);
      const e = combatants.find((c) => c && String(c.id) === tid);
      if (!e) return null;
      const enemy_key = e.enemy_key != null ? String(e.enemy_key).trim() : "";
      const target_name = e.name != null ? String(e.name).trim() : "";
      const defenseRaw = e.defense != null ? Number(e.defense) : null;
      const defense = Number.isFinite(defenseRaw) ? defenseRaw : null;
      return { target_id: tid, enemy_key, target_name, defense };
    }

    _syncCombatDebugEnemyHintFromState(st) {
      if (typeof window === "undefined" || !window.state) return;
      const combatants = Array.isArray(st?.combatants) ? st.combatants : [];
      const enemies = combatants.filter((c) => c && c.type === "enemy");
      if (!enemies.length) return;
      const hint = enemies
        .map((e) => {
          const k = String(e.enemy_key || e.id || "?").trim() || "?";
          const lab = String(e.name || e.label || k).trim() || k;
          return `${k} — ${lab}`;
        })
        .join("; ");
      window.state._combatDebugEnemyHint = hint;
    }

    _defenseForCombatLogRow(row) {
      const combatants = Array.isArray(this._state?.combatants) ? this._state.combatants : [];
      const tid = row.target_id != null ? String(row.target_id) : "";
      if (!tid) return null;
      const e = combatants.find((c) => c && String(c.id) === tid);
      if (!e || e.type !== "enemy") return null;
      const d = e.defense != null ? Number(e.defense) : null;
      return Number.isFinite(d) ? d : null;
    }

    _formatCombatEngineRow(row) {
      if (!row) return "";
      const evt = String(row.event_type || "");
      const actor = String(row.actor || "");
      if (evt === "death") {
        const nar = String(row.narrative || "").trim() || "Wróg eliminowany.";
        return `<div class="combat-engine-turn">
          <div class="combat-engine-turn__head">💀 ${esc(nar)}</div>
        </div>`;
      }
      if (evt !== "attack") return "";
      const hit = row.hit === 1 || row.hit === true;
      const rv = row.roll_value != null ? Number(row.roll_value) : null;
      const dmg = row.damage != null ? Number(row.damage) : null;
      const tgt = String(row.target_name || "").trim() || "—";
      if (actor === "player") {
        const ac = this._defenseForCombatLogRow(row);
        const acBit = ac != null ? ` vs AC ${ac}` : "";
        const hitLine = hit
          ? `✅ TRAFIENIE · obrażenia: ${dmg != null ? dmg : "?"}`
          : "❌ PUDŁO";
        return `<div class="combat-engine-turn combat-engine-turn--player">
          <div class="combat-engine-turn__head">⚔️ ATAK GRACZA → ${esc(tgt)}</div>
          <div class="combat-engine-turn__detail">Rzut: ${Number.isFinite(rv) ? rv : "—"}${acBit} → ${hitLine}</div>
        </div>`;
      }
      if (actor === "enemy") {
        let rawD20 = null;
        let pac = null;
        let enemyName = "";
        try {
          const meta =
            typeof row.narrative === "string" && row.narrative.trim()
              ? JSON.parse(row.narrative)
              : {};
          rawD20 = meta.raw_d20 != null ? Number(meta.raw_d20) : null;
          pac = meta.target_ac != null ? Number(meta.target_ac) : null;
          enemyName = String(meta.enemy_name || "").trim();
        } catch (_e) {
          /* ignore */
        }
        const d20s = Number.isFinite(rawD20) ? String(rawD20) : "—";
        const acs = Number.isFinite(pac) ? String(pac) : "—";
        const hitLine = hit
          ? `✅ TRAFIENIE · obrażenia: ${dmg != null ? dmg : "?"}`
          : "❌ PUDŁO";
        const label = enemyName || (tgt && tgt !== "Gracz" ? tgt : "Wróg");
        return `<div class="combat-engine-turn combat-engine-turn--enemy">
          <div class="combat-engine-turn__head">🗡️ ATAK WROGA — ${esc(label)}</div>
          <div class="combat-engine-turn__detail">Rzut: ${d20s} vs AC gracza ${acs} → ${hitLine}</div>
        </div>`;
      }
      return "";
    }

    async _refreshCombatEngineTurnsPanel() {
      const el = this._host?.querySelector("#combat-engine-turns");
      if (!el) return;
      const cid = this._campaignId();
      if (!cid || !this._state || String(this._state.status) !== "active") {
        el.innerHTML = "";
        el.hidden = true;
        return;
      }
      try {
        const res = await fetch(`/api/campaigns/${cid}/combat/turns`, {
          headers: window.getApiHeaders ? window.getApiHeaders() : {},
        });
        if (!res.ok) {
          el.hidden = true;
          return;
        }
        const data = await res.json().catch(() => ({}));
        const rows = Array.isArray(data.turns) ? data.turns : [];
        const interesting = rows.filter(
          (r) => r && (String(r.event_type) === "attack" || String(r.event_type) === "death")
        );
        if (!interesting.length) {
          el.innerHTML = "";
          el.hidden = true;
          return;
        }
        el.hidden = false;
        el.innerHTML =
          '<div class="combat-engine-turns-title">Tury silnika</div>' +
          interesting.map((r) => this._formatCombatEngineRow(r)).join("");
      } catch (_e) {
        el.hidden = true;
      }
    }

    async _onAttack() {
      if (!this._state || this._state.status !== "active") {
        this._setMsg("Brak aktywnej walki.", true);
        return;
      }
      if (this._state.current_turn !== "player") {
        this._setMsg("Nie twoja tura.", true);
        return;
      }
      const cid = this._campaignId();
      if (!cid || this._busy) return;
      this._busy = true;
      this._setMsg("");
      if (this._state) this.render(this._state);
      try {
        const { inputEl } = window.getEls ? window.getEls() : {};
        const intentRaw = inputEl ? String(inputEl.value || "").trim() : "";

        if (typeof window.loadCharacterSheet === "function" && window.state.selectedCharacterId) {
          await window.loadCharacterSheet(window.state.selectedCharacterId);
        }
        const sheet = window.state.characterSheet || {};
        const str = Number(sheet.stats?.STR ?? 10);
        const mod = window.getStatModifier ? window.getStatModifier(str) : Math.floor((str - 10) / 2);

        const diceResp = await fetch("/api/gm/dice", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dice: "1d20" }),
        });
        if (!diceResp.ok) throw new Error(`Kość: HTTP ${diceResp.status}`);
        const diceData = await diceResp.json();
        const d20 = Number(diceData.total ?? 0);
        const total = d20 + mod;

        const atkTarget = this._currentPlayerAttackTarget();
        const resolveBody = {
          roll_result: total,
          raw_d20: d20,
          attacker: "player",
        };
        if (atkTarget && atkTarget.enemy_key) {
          resolveBody.enemy_key = atkTarget.enemy_key;
        }
        if (atkTarget && atkTarget.target_id) {
          resolveBody.target_id = atkTarget.target_id;
        }

        const res = await fetch(`/api/campaigns/${cid}/combat/resolve-attack`, {
          method: "POST",
          headers: window.getApiHeaders ? window.getApiHeaders() : { "Content-Type": "application/json" },
          body: JSON.stringify(resolveBody),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

        const cs = data.combat_state || null;
        const endedNow = cs && String(cs.status) === "ended";
        const victoryNarrationFirst =
          endedNow && String(cs.ended_reason || "") === "victory";

        if (data.hit) {
          this._setMsg(`Trafienie! ${data.damage ?? "?"} obrażeń`);
        } else if (data.player_nat1) {
          this._setMsg("Fatalne pudło!");
        } else if (data.dodged) {
          this._setMsg("Wróg unika ciosu!");
        } else {
          this._setMsg("Pudło!");
        }

        const natRoll = Number(d20);
        if (natRoll === 20) {
          this._flashElement(this._card, "combat-flash-crit", 400);
        } else if (natRoll === 1) {
          this._flashElement(this._card, "combat-flash-fumble", 400);
        } else if (data.hit) {
          // Enemy rows are rebuilt via innerHTML in render(), so flash stable panel node instead.
          this._flashElement(this._card, "combat-flash-hit", 300);
        }

        if (data.enemy_dead) {
          const goldDrop = Math.max(0, Number(data.gold_drop || 0));
          this._pendingLoot = Array.isArray(data.loot) ? data.loot.slice() : [];
          if (victoryNarrationFirst) {
            this._pendingGold = goldDrop;
          } else {
            this._pendingGold = 0;
          }
        }

        const charName =
          typeof window.currentCharacterName === "function"
            ? window.currentCharacterName()
            : String(sheet.name || "Bohater");
        const enemyAc =
          atkTarget && atkTarget.defense != null ? Number(atkTarget.defense) : null;
        const dataForCard = {
          ...data,
          target_ac:
            data.target_ac != null && Number.isFinite(Number(data.target_ac))
              ? Number(data.target_ac)
              : Number.isFinite(enemyAc)
                ? enemyAc
                : null,
        };
        const dbLine = this._playerAttackRollDbLine(
          intentRaw,
          charName,
          d20,
          mod,
          total,
          dataForCard,
          endedNow
        );
        const turnNum =
          typeof window.nextTurnNumber === "function" ? window.nextTurnNumber() : null;
        this._appendCombatAttackRollUserChatLine(dbLine, charName, turnNum);

        if (cs) {
          this._state = cs;
          if (victoryNarrationFirst) {
            this._deferVictoryOverlay = true;
          }
          this.render(cs);
        }

        await this._sendCombatNarrativeFollowUp(dbLine);

        if (endedNow) {
          if (typeof window.combatInput?.syncWithCombat === "function") {
            window.combatInput.syncWithCombat(null);
          }
          if (!victoryNarrationFirst) {
            const pool =
              Array.isArray(cs?.loot_pool) && cs.loot_pool.length
                ? cs.loot_pool.slice()
                : Array.isArray(data.loot)
                  ? data.loot.slice()
                  : [];
            if (pool.length > 0) {
              const claimed = await this._showLootPopupAsync(
                pool,
                Math.max(0, Number(data.gold_drop || 0))
              );
              this._accumulatedLoot = Array.isArray(claimed) ? claimed.slice() : [];
              await this._runPostLootNarration(
                Array.isArray(claimed) ? claimed.length : 0,
                pool.length
              );
            } else if (Math.max(0, Number(data.gold_drop || 0)) > 0) {
              await this._showLootPopupAsync([], Math.max(0, Number(data.gold_drop || 0)));
            }
            if (typeof window.refreshInventoryPanel === "function") {
              window.refreshInventoryPanel();
            }
            this.showVictory(cs);
          }
          return;
        }
      } catch (e) {
        this._setMsg(e.message || "Atak nie powiódł się.", true);
      } finally {
        this._busy = false;
        if (this._state) this.render(this._state);
      }
    }
  }

  window.CombatPanel = CombatPanel;
  window.combatPanel = new CombatPanel();

  window.afterTurnsLoaded = async function (campaignId) {
    const cid = window.state?.selectedCampaignId;
    if (!cid || Number(cid) !== Number(campaignId)) return;
    await window.combatPanel.fetchAndMaybeShow();
  };

  window.applyCombatInitiatedFromTurn = function (combatState) {
    window.combatPanel.applyCombatInitiated(combatState);
  };
})();
