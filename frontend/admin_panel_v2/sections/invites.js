/* Stage 11-C C15 — Invite tree + invite management */

export async function init(panel) {
    panel.innerHTML = renderInvitesSection();
    await loadInviteData();
    bindEvents();
}

function renderInvitesSection() {
    return `
<div class="section-header">
  <h2 class="section-title">🌳 Drzewo Zaproszeń</h2>
</div>

<div class="card" style="padding: 20px; margin-bottom: 20px;">
  <h3 style="margin-bottom: 12px; font-size: 0.85rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Stwórz nowe zaproszenie</h3>
  <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end;">
    <div style="flex: 1; min-width: 180px;">
      <label class="form-label">Email (opcjonalny)</label>
      <input type="email" id="inv-email" class="form-input" placeholder="znajomy@email.com">
    </div>
    <div style="flex: 2; min-width: 200px;">
      <label class="form-label">Wiadomość osobista (opcjonalna)</label>
      <input type="text" id="inv-msg" class="form-input" placeholder="Dołącz do przygody!">
    </div>
    <button class="btn btn-primary" id="inv-create-btn">+ Utwórz</button>
  </div>
  <div id="inv-result" style="display:none; margin-top: 12px; padding: 12px; background: rgba(34,167,70,0.1); border: 1px solid rgba(34,167,70,0.3); border-radius: 6px;">
    <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 8px;">Link zaproszenia (skopiuj i wyślij):</div>
    <div style="display: flex; gap: 8px;">
      <input type="text" id="inv-link-out" style="flex:1; background: transparent; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; padding: 6px 10px; color: #4caf78; font-size: 0.85rem; font-family: monospace;" readonly>
      <button id="inv-copy-btn" class="btn btn-secondary" style="padding: 6px 14px; font-size: 0.8rem;">Kopiuj</button>
    </div>
  </div>
</div>

<!-- Tabs -->
<div class="inv-tabs" style="display: flex; gap: 0; border-bottom: 1px solid var(--border, #333); margin-bottom: 20px;">
  <button class="inv-tab inv-tab--active" data-tab="tree">🌳 Drzewo</button>
  <button class="inv-tab" data-tab="list">📋 Lista zaproszeń</button>
</div>

<div id="inv-tab-tree">
  <div id="invite-tree-svg-wrap" style="overflow-x: auto; min-height: 300px; background: rgba(0,0,0,0.2); border-radius: 8px; padding: 16px; position: relative;">
    <div id="inv-tree-loading" style="text-align: center; padding: 60px; color: var(--text-muted);">Ładowanie drzewa...</div>
    <svg id="invite-tree-svg" style="display:block;"></svg>
  </div>
  <div style="margin-top: 12px; display: flex; gap: 16px; font-size: 0.8rem; color: var(--text-muted);">
    <span><span style="color:#4caf78">●</span> Aktywny (&lt;30 dni, ≥10 tur)</span>
    <span><span style="color:#c9944a">●</span> Mało aktywny (1–9 tur)</span>
    <span><span style="color:#6b665e">●</span> Nieaktywny (brak tur lub &gt;30 dni)</span>
  </div>
</div>

<div id="inv-tab-list" style="display:none">
  <table class="admin-table" id="inv-table">
    <thead><tr>
      <th>Email</th><th>Stworzył</th><th>Ważne do</th><th>Status</th><th></th>
    </tr></thead>
    <tbody id="inv-table-body"><tr><td colspan="5" style="text-align:center;color:var(--text-muted)">Ładowanie...</td></tr></tbody>
  </table>
</div>
`;
}

async function loadInviteData() {
    await Promise.all([renderInviteTree(), renderInviteList()]);
}

async function renderInviteTree() {
    // Load D3 dynamically only once
    if (!window.d3) {
        await new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = 'https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js';
            s.onload = resolve;
            s.onerror = reject;
            document.head.appendChild(s);
        });
    }

    const { adminFetch } = await import('../shared/api.js');
    let treeData;
    try {
        const resp = await adminFetch('/api/admin/invite-tree');
        // Backend returns { tree: <node or array> }
        treeData = resp.tree;
    } catch (e) {
        document.getElementById('inv-tree-loading').textContent = 'Błąd ładowania: ' + (e.message || 'nieznany');
        return;
    }

    const loadingEl = document.getElementById('inv-tree-loading');
    if (loadingEl) loadingEl.style.display = 'none';

    if (!treeData || (Array.isArray(treeData) && treeData.length === 0)) {
        const wrap = document.getElementById('invite-tree-svg-wrap');
        if (wrap) wrap.innerHTML = '<div style="text-align:center;padding:60px;color:var(--text-muted)">Brak danych drzewa zaproszeń</div>';
        return;
    }

    // If backend returned an array (multiple roots), wrap in a virtual root
    const rootData = Array.isArray(treeData)
        ? { id: 0, name: 'AI-GM', username: 'root', status: 'active', turns: 0, children: treeData }
        : treeData;

    drawTree(rootData);
}

function drawTree(rootData) {
    const d3 = window.d3;
    const wrap = document.getElementById('invite-tree-svg-wrap');
    if (!wrap) return;

    // Clear any previous SVG content
    const svgEl = document.getElementById('invite-tree-svg');
    if (svgEl) svgEl.innerHTML = '';

    const activityColor = { active: '#4caf78', low: '#c9944a', cold: '#6b665e' };

    const margin = { top: 24, right: 140, bottom: 24, left: 100 };
    const dx = 44;  // vertical spacing per node
    const dy = 180; // horizontal level spacing

    const root = d3.hierarchy(rootData);

    // Collapse all nodes except root and first level by default
    root.descendants().forEach(d => {
        if (d.depth > 1) {
            d._children = d.children;
            d.children = null;
        }
    });

    const tree = d3.tree().nodeSize([dx, dy]);

    // Build SVG with a "g" group for panning
    const svg = d3.select('#invite-tree-svg');
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Link path generator
    const linkGen = d3.linkHorizontal().x(d => d.y).y(d => d.x);

    // Groups for links and nodes (links below nodes)
    const gLinks = g.append('g').attr('class', 'inv-links').attr('fill', 'none').attr('stroke', '#3a3d50').attr('stroke-width', 1.5);
    const gNodes = g.append('g').attr('class', 'inv-nodes').attr('cursor', 'pointer');

    function update(source) {
        tree(root);

        // Compute bounds
        let x0 = Infinity, x1 = -Infinity;
        root.each(d => {
            if (d.x > x1) x1 = d.x;
            if (d.x < x0) x0 = d.x;
        });

        const height = x1 - x0 + margin.top + margin.bottom + dx * 2;
        const width = root.height * dy + margin.left + margin.right + 60;

        svg.attr('width', Math.max(width, 400))
           .attr('height', Math.max(height, 200));

        // Offset group so tree fits
        g.attr('transform', `translate(${margin.left},${margin.top + (-x0 + dx)})`);

        // ── Links ──
        const links = gLinks.selectAll('path').data(root.links(), d => d.target.data.id);

        links.enter().append('path')
            .attr('opacity', 0)
            .attr('d', () => {
                const o = { x: source.x0 ?? source.x, y: source.y0 ?? source.y };
                return linkGen({ source: o, target: o });
            })
            .merge(links)
            .transition().duration(250)
            .attr('opacity', 1)
            .attr('d', linkGen);

        links.exit()
            .transition().duration(250)
            .attr('opacity', 0)
            .attr('d', () => {
                const o = { x: source.x, y: source.y };
                return linkGen({ source: o, target: o });
            })
            .remove();

        // ── Nodes ──
        const nodes = gNodes.selectAll('g.inv-node').data(root.descendants(), d => d.data.id);

        const nodeEnter = nodes.enter().append('g')
            .attr('class', 'inv-node')
            .attr('transform', () => `translate(${source.y0 ?? source.y},${source.x0 ?? source.x})`)
            .attr('opacity', 0)
            .on('click', (event, d) => {
                // Toggle children
                if (d._children || d.children) {
                    if (d.children) {
                        d._children = d.children;
                        d.children = null;
                    } else {
                        d.children = d._children;
                        d._children = null;
                    }
                    update(d);
                }
            });

        // Outer ring for collapsed-indicator
        nodeEnter.append('circle')
            .attr('r', 10)
            .attr('fill', 'transparent')
            .attr('stroke', d => activityColor[d.data.status] || '#6b665e')
            .attr('stroke-width', d => d._children ? 2 : 0)
            .attr('stroke-dasharray', '3,2');

        // Main node circle
        nodeEnter.append('circle')
            .attr('class', 'inv-node-circle')
            .attr('r', 6)
            .attr('fill', d => activityColor[d.data.status] || '#6b665e')
            .attr('stroke', '#0f1117')
            .attr('stroke-width', 1.5);

        // Username label
        nodeEnter.append('text')
            .attr('class', 'inv-node-label')
            .attr('dy', '0.32em')
            .attr('x', d => (d.children || d._children) ? -14 : 14)
            .attr('text-anchor', d => (d.children || d._children) ? 'end' : 'start')
            .attr('fill', '#c9a54a')
            .attr('font-size', '12px')
            .text(d => d.data.name || d.data.username);

        // Turns count badge (small)
        nodeEnter.append('text')
            .attr('class', 'inv-node-turns')
            .attr('dy', '0.32em')
            .attr('y', -13)
            .attr('text-anchor', 'middle')
            .attr('fill', d => activityColor[d.data.status] || '#6b665e')
            .attr('font-size', '10px')
            .text(d => d.data.turns > 0 ? `${d.data.turns}t` : '');

        // Merge enter + existing
        const nodeMerge = nodeEnter.merge(nodes);

        nodeMerge.transition().duration(250)
            .attr('transform', d => `translate(${d.y},${d.x})`)
            .attr('opacity', 1);

        // Update circles and labels after toggle
        nodeMerge.select('circle.inv-node-circle')
            .attr('fill', d => activityColor[d.data.status] || '#6b665e');

        nodeMerge.select('circle:first-child')
            .attr('stroke-width', d => d._children ? 2 : 0);

        nodeMerge.select('text.inv-node-label')
            .attr('x', d => (d.children || d._children) ? -14 : 14)
            .attr('text-anchor', d => (d.children || d._children) ? 'end' : 'start');

        nodes.exit()
            .transition().duration(250)
            .attr('transform', () => `translate(${source.y},${source.x})`)
            .attr('opacity', 0)
            .remove();

        // Save positions for next transition origin
        root.each(d => { d.x0 = d.x; d.y0 = d.y; });
    }

    // Initial draw
    root.x0 = 0;
    root.y0 = 0;
    update(root);
}

async function renderInviteList() {
    const { adminFetch } = await import('../shared/api.js');
    const { showToast } = await import('../shared/toast.js');
    try {
        const resp = await adminFetch('/api/admin/invites');
        // Backend returns { invites: [...] }
        const invites = resp.invites || [];
        const tbody = document.getElementById('inv-table-body');
        if (!invites.length) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">Brak zaproszeń</td></tr>';
            return;
        }
        tbody.innerHTML = invites.map(inv => {
            const used = !!inv.used_at;
            const expired = !used && inv.expires_at && new Date(inv.expires_at) < new Date();
            const status = used
                ? '<span style="color:#6b665e">Użyte</span>'
                : expired
                    ? '<span style="color:#c94a4a">Wygasłe</span>'
                    : '<span style="color:#4caf78">Aktywne</span>';
            const expiry = inv.expires_at ? new Date(inv.expires_at).toLocaleDateString('pl') : '—';
            // Backend field: creator_name (not inviter_name)
            const creator = inv.creator_name || '—';
            const revokeBtn = (!used && !expired)
                ? `<button class="btn btn-danger" style="padding:4px 10px;font-size:0.8rem" onclick="window._invRevoke(${inv.id})">Odwołaj</button>`
                : '';
            return `<tr>
                <td>${inv.email || '<em style="color:var(--text-muted)">otwarty</em>'}</td>
                <td>${creator}</td>
                <td>${expiry}</td>
                <td>${status}</td>
                <td>${revokeBtn}</td>
            </tr>`;
        }).join('');

        // Wire revoke globally (scoped name to avoid collision)
        window._invRevoke = async (id) => {
            if (!confirm('Odwołać zaproszenie?')) return;
            try {
                await adminFetch(`/api/admin/invites/${id}`, { method: 'DELETE' });
                showToast('Zaproszenie odwołane', 'success');
                await renderInviteList();
            } catch (e) {
                showToast(e.message || 'Błąd', 'error');
            }
        };
    } catch (e) {
        const tbody = document.getElementById('inv-table-body');
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="5" style="color:#c94a4a">${e.message}</td></tr>`;
        }
    }
}

function bindEvents() {
    // Tab switching
    document.querySelectorAll('.inv-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.inv-tab').forEach(b => b.classList.remove('inv-tab--active'));
            btn.classList.add('inv-tab--active');
            const isTree = btn.dataset.tab === 'tree';
            document.getElementById('inv-tab-tree').style.display = isTree ? '' : 'none';
            document.getElementById('inv-tab-list').style.display = isTree ? 'none' : '';
        });
    });

    // Create invite button
    const createBtn = document.getElementById('inv-create-btn');
    if (createBtn) createBtn.addEventListener('click', createInvite);

    // Copy button
    const copyBtn = document.getElementById('inv-copy-btn');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const input = document.getElementById('inv-link-out');
            if (!input) return;
            input.select();
            navigator.clipboard?.writeText(input.value).catch(() => document.execCommand('copy'));
            copyBtn.textContent = 'Skopiowano!';
            setTimeout(() => { copyBtn.textContent = 'Kopiuj'; }, 2000);
        });
    }
}

async function createInvite() {
    const { adminFetch } = await import('../shared/api.js');
    const { showToast } = await import('../shared/toast.js');
    const email = (document.getElementById('inv-email')?.value || '').trim();
    const message = (document.getElementById('inv-msg')?.value || '').trim();
    const btn = document.getElementById('inv-create-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Tworzenie...'; }
    try {
        const resp = await adminFetch('/api/admin/invites', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email || null, message: message || null }),
        });
        const linkOut = document.getElementById('inv-link-out');
        const result = document.getElementById('inv-result');
        if (linkOut) linkOut.value = resp.invite_link || resp.code || '';
        if (result) result.style.display = 'block';
        const emailEl = document.getElementById('inv-email');
        const msgEl = document.getElementById('inv-msg');
        if (emailEl) emailEl.value = '';
        if (msgEl) msgEl.value = '';
        showToast('Zaproszenie utworzone', 'success');
        // Refresh both tabs
        await Promise.all([renderInviteList(), renderInviteTree()]);
    } catch (e) {
        showToast(e.message || 'Błąd tworzenia zaproszenia', 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '+ Utwórz'; }
    }
}
