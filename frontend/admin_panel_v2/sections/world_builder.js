/**
 * World Builder v2 — Hex Grid Map Editor (Task 40)
 * Uses SVG hex rendering. Replaces the old Cytoscape.js node-graph.
 */
import { adminFetch } from "/admin_panel_v2/shared/api.js?v=3";
import { showToast } from "/admin_panel_v2/shared/toast.js?v=1";

let _hexTypes = {};
let _hexes = {};
let _teleports = [];
let _selectedHex = null;
let _paintType = "forest";
let _drawingTeleport = null;
let _svg = null;
let _zoom = 1.0;
let _pan = { x: 400, y: 280 };
let _isDragging = false;
let _dragStart = null;
let _container = null;

const HEX_SIZE = 40;

// ── Hex geometry (flat-top) ───────────────────────────────────────────────────

function hexToPixel(q, r) {
  return { x: HEX_SIZE * 1.5 * q, y: HEX_SIZE * (Math.sqrt(3)/2 * q + Math.sqrt(3) * r) };
}

function hexRound(q, r) {
  const s = -q - r;
  let rq = Math.round(q), rr = Math.round(r), rs = Math.round(s);
  const dq=Math.abs(rq-q),dr=Math.abs(rr-r),ds=Math.abs(rs-s);
  if(dq>dr&&dq>ds) rq=-rr-rs; else if(dr>ds) rr=-rq-rs;
  return { q:rq, r:rr };
}

function hexCorners(cx, cy, size) {
  return Array.from({length:6},(_,i)=>{
    const a = Math.PI/180*60*i;
    return `${cx+size*Math.cos(a)},${cy+size*Math.sin(a)}`;
  }).join(" ");
}

function hexKey(q, r) { return `${q},${r}`; }
function hexNeighbors(q, r) {
  return [[1,0],[-1,0],[0,1],[0,-1],[1,-1],[-1,1]].map(([dq,dr])=>({q:q+dq,r:r+dr}));
}

function _ws(wx, wy) { return { x: wx*_zoom+_pan.x, y: wy*_zoom+_pan.y }; }

// ── Render ────────────────────────────────────────────────────────────────────

function _render() {
  if(!_svg) return;
  let html = "";

  // Painted hexes
  for(const hex of Object.values(_hexes)) {
    const {x,y} = hexToPixel(hex.q, hex.r);
    const {x:sx,y:sy} = _ws(x,y);
    const rz = HEX_SIZE*_zoom;
    const cfg = _hexTypes[hex.hex_type]||{map_color:"#4a6a4a",map_icon:""};
    const sel = _selectedHex&&_selectedHex.q===hex.q&&_selectedHex.r===hex.r;
    html += `<polygon class="hx" data-q="${hex.q}" data-r="${hex.r}"
      points="${hexCorners(sx,sy,rz-1)}"
      fill="${cfg.map_color}" stroke="${sel?"#f0c040":"#222"}" stroke-width="${sel?2:0.7}"
      style="cursor:pointer"/>`;
    if(_zoom>=0.45&&cfg.map_icon)
      html += `<text x="${sx}" y="${sy-rz*0.05}" text-anchor="middle"
        font-size="${Math.max(9,13*_zoom)}" style="pointer-events:none">${cfg.map_icon}</text>`;
    if(_zoom>=0.5&&hex.label)
      html += `<text x="${sx}" y="${sy+rz*0.38}" text-anchor="middle"
        font-size="${Math.max(7,9*_zoom)}" fill="#c8c0a8" style="pointer-events:none">${_e(hex.label.slice(0,14))}</text>`;
  }

  // Ghost (adjacent empties)
  if(_zoom>=0.3) {
    const placed = new Set(Object.keys(_hexes));
    const ghosts = new Set();
    for(const h of Object.values(_hexes))
      for(const n of hexNeighbors(h.q,h.r))
        if(!placed.has(hexKey(n.q,n.r))) ghosts.add(hexKey(n.q,n.r));
    for(const k of ghosts) {
      const [q,r]=k.split(",").map(Number);
      const {x,y}=hexToPixel(q,r);
      const {x:sx,y:sy}=_ws(x,y);
      html += `<polygon class="hg" data-q="${q}" data-r="${r}"
        points="${hexCorners(sx,sy,HEX_SIZE*_zoom-1)}"
        fill="transparent" stroke="#2a2a3a" stroke-width="0.5" stroke-dasharray="3,3"
        style="cursor:crosshair"/>`;
    }
  }

  // Teleport connections
  for(const t of _teleports) {
    const p1=hexToPixel(t.from_q,t.from_r), p2=hexToPixel(t.to_q,t.to_r);
    const s1=_ws(p1.x,p1.y), s2=_ws(p2.x,p2.y);
    const mx=(s1.x+s2.x)/2, my=(s1.y+s2.y)/2-28*_zoom;
    const colors={boat:"#3a8aaa",magic:"#8a3aaa",tunnel:"#8a6a3a",portal:"#3aaa6a"};
    const col=colors[t.travel_type]||"#888";
    html += `<path d="M${s1.x},${s1.y} Q${mx},${my} ${s2.x},${s2.y}"
      fill="none" stroke="${col}" stroke-width="${1.4*_zoom}" stroke-dasharray="5,3"
      style="pointer-events:none"/>`;
    if(_zoom>=0.55&&t.label)
      html += `<text x="${mx}" y="${my-4}" text-anchor="middle"
        font-size="${Math.max(7,8*_zoom)}" fill="${col}" style="pointer-events:none">${_e(t.label)}</text>`;
  }

  _svg.innerHTML = html;
  _svg.querySelectorAll(".hx,.hg").forEach(el=>el.addEventListener("click",_onHexClick));
  _container.querySelector("#wb-zoom-label").textContent = `Zoom: ${Math.round(_zoom*100)}%`;
}

function _e(s){return String(s??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

// ── Data ──────────────────────────────────────────────────────────────────────

async function _load() {
  const [m,t] = await Promise.all([
    adminFetch("/api/admin/world/map"),
    adminFetch("/api/admin/world/hex-types"),
  ]);
  _hexes={};
  for(const h of (m.hexes||[])) _hexes[hexKey(h.q,h.r)]=h;
  _teleports=m.teleport_connections||[];
  _hexTypes={};
  for(const t2 of (t.hex_types||[])) _hexTypes[t2.hex_type]=t2;
}

// ── Interaction ───────────────────────────────────────────────────────────────

async function _onHexClick(e) {
  const q=parseInt(e.target.dataset.q), r=parseInt(e.target.dataset.r);
  if(_drawingTeleport) {
    if(_drawingTeleport.q===q&&_drawingTeleport.r===r) {
      _drawingTeleport=null; showToast("Anulowano.","info"); return;
    }
    await _createTeleport(_drawingTeleport.q,_drawingTeleport.r,q,r);
    _drawingTeleport=null; return;
  }
  if(_hexes[hexKey(q,r)]) { _selectedHex={q,r}; _render(); _renderDetail(_hexes[hexKey(q,r)]); }
  else await _paint(q,r);
}

async function _paint(q,r) {
  try {
    const cfg=_hexTypes[_paintType]||{};
    const res=await adminFetch("/api/admin/world/hexes",{
      method:"POST",body:JSON.stringify({q,r,hex_type:_paintType,encounter_chance:cfg.encounter_base_chance||0.15})
    });
    _hexes[hexKey(q,r)]=res.hex;
    _selectedHex={q,r}; _render(); _renderDetail(res.hex);
    showToast(`${cfg.label||_paintType} dodany.`,"success");
  } catch(e){showToast(e.message||"Błąd","error");}
}

async function _deleteHex(q,r) {
  if(!confirm(`Usunąć hex (${q},${r})?`)) return;
  try {
    await adminFetch(`/api/admin/world/hexes/${q}/${r}`,{method:"DELETE"});
    delete _hexes[hexKey(q,r)]; _selectedHex=null; _render(); _clearDetail();
    showToast("Hex usunięty.","success");
  } catch(e){showToast(e.message||"Błąd","error");}
}

async function _saveHex(q,r,updates) {
  try {
    const res=await adminFetch(`/api/admin/world/hexes/${q}/${r}`,{method:"PATCH",body:JSON.stringify(updates)});
    _hexes[hexKey(q,r)]=res.hex; _render(); _renderDetail(res.hex);
    showToast("Zapisano.","success");
  } catch(e){showToast(e.message||"Błąd","error");}
}

async function _createTeleport(fq,fr,tq,tr) {
  const type=prompt("Typ: boat | magic | tunnel | portal","boat")||"boat";
  const hours=parseFloat(prompt("Czas (h):","8")||"8");
  const label=prompt("Etykieta (opcjonalna):","")?.trim()||null;
  try {
    const res=await adminFetch("/api/admin/world/teleport-connections",{
      method:"POST",body:JSON.stringify({from_q:fq,from_r:fr,to_q:tq,to_r:tr,travel_type:type,travel_hours:hours,label})
    });
    _teleports.push(res.connection); _render(); showToast(`Połączenie ${type} dodane.`,"success");
  } catch(e){showToast(e.message||"Błąd","error");}
}

// ── Detail panel ──────────────────────────────────────────────────────────────

function _renderDetail(hex) {
  const p=_container.querySelector(".wb-detail");
  if(!p) return;
  const cfg=_hexTypes[hex.hex_type]||{};
  const pool=(Array.isArray(hex.encounter_pool)?hex.encounter_pool:[]).join(",");
  const myTeleports=_teleports.filter(t=>(t.from_q===hex.q&&t.from_r===hex.r)||(t.to_q===hex.q&&t.to_r===hex.r));

  p.innerHTML=`
    <div class="wb-dh">
      <span>${cfg.map_icon||"⬡"} (${hex.q},${hex.r})</span>
      <button class="icon-btn" id="wbd-del">🗑</button>
    </div>
    <label class="wb-lbl">Typ terenu</label>
    <select id="wbd-type">${Object.entries(_hexTypes).map(([k,v])=>
      `<option value="${k}"${k===hex.hex_type?" selected":""}>${v.map_icon||""} ${v.label}</option>`).join("")}</select>
    <label class="wb-lbl">Etykieta</label>
    <input id="wbd-label" type="text" value="${_e(hex.label||"")}" placeholder="np. Thornwood"/>
    <label class="wb-lbl">Atmosfera</label>
    <textarea id="wbd-atm" rows="2">${_e(hex.atmosphere||"")}</textarea>
    <label class="wb-lbl">Szansa spotkania</label>
    <input id="wbd-enc" type="number" value="${hex.encounter_chance}" min="0" max="1" step="0.05"/>
    <label class="wb-lbl">Wrogowie (klucze, przecinkami)</label>
    <input id="wbd-pool" type="text" value="${_e(pool)}"/>
    <div style="display:flex;gap:6px;margin-top:10px">
      <button class="primary-btn" id="wbd-save" style="flex:1">Zapisz</button>
      <button class="secondary-btn" id="wbd-tp">⤷ Połącz</button>
    </div>
    <div style="margin-top:10px;font-size:0.72rem;color:var(--text-muted)">Połączenia specjalne:</div>
    ${myTeleports.length?myTeleports.map(t=>{
      const other=(t.from_q===hex.q&&t.from_r===hex.r)?`→(${t.to_q},${t.to_r})`:`←(${t.from_q},${t.from_r})`;
      return `<div style="display:flex;align-items:center;gap:6px;font-size:0.72rem;margin:2px 0">
        <span style="flex:1">${t.travel_type} ${other} ${t.travel_hours}h</span>
        <button class="icon-btn wbd-del-tp" data-id="${t.id}" style="font-size:0.65rem">✕</button>
      </div>`;
    }).join(""):`<span style="font-size:0.72rem;color:var(--text-muted)">Brak</span>`}`;

  p.querySelector("#wbd-del").onclick=()=>_deleteHex(hex.q,hex.r);
  p.querySelector("#wbd-save").onclick=()=>_saveHex(hex.q,hex.r,{
    hex_type:p.querySelector("#wbd-type").value,
    label:p.querySelector("#wbd-label").value.trim()||null,
    atmosphere:p.querySelector("#wbd-atm").value.trim()||null,
    encounter_chance:parseFloat(p.querySelector("#wbd-enc").value)||0.15,
    encounter_pool:p.querySelector("#wbd-pool").value.split(",").map(s=>s.trim()).filter(Boolean),
  });
  p.querySelector("#wbd-tp").onclick=()=>{
    _drawingTeleport={q:hex.q,r:hex.r};
    showToast("Kliknij docelowy hex. Kliknij ten sam → anuluj.","info");
  };
  p.querySelectorAll(".wbd-del-tp").forEach(b=>b.onclick=async()=>{
    const id=parseInt(b.dataset.id);
    try{
      await adminFetch(`/api/admin/world/teleport-connections/${id}`,{method:"DELETE"});
      _teleports=_teleports.filter(t=>t.id!==id); _render(); _renderDetail(_hexes[hexKey(hex.q,hex.r)]);
      showToast("Połączenie usunięte.","success");
    }catch(e){showToast(e.message,"error");}
  });
}

function _clearDetail() {
  const p=_container.querySelector(".wb-detail");
  if(p) p.innerHTML=`<div style="color:var(--text-muted);padding:12px;font-size:0.82rem">Kliknij hex aby edytować lub puste miejsce aby pomalować.</div>`;
}

function _renderPalette() {
  const pal=_container.querySelector(".wb-palette");
  if(!pal) return;
  pal.innerHTML=Object.entries(_hexTypes).map(([k,v])=>
    `<button class="wb-pb${_paintType===k?" active":""}" data-type="${k}"
      style="background:${v.map_color};color:#e8e4dc" title="${v.label} ${v.travel_hours}h">${v.map_icon||"⬡"}</button>`
  ).join("");
  pal.querySelectorAll(".wb-pb").forEach(b=>b.onclick=()=>{
    _paintType=b.dataset.type; _drawingTeleport=null; _renderPalette();
  });
}

// ── Pan / zoom ────────────────────────────────────────────────────────────────

function _onWheel(e) {
  e.preventDefault();
  const rect=_svg.getBoundingClientRect();
  const mx=e.clientX-rect.left, my=e.clientY-rect.top;
  const f=e.deltaY<0?1.15:0.87;
  const nz=Math.max(0.12,Math.min(5,_zoom*f));
  _pan.x=mx-(mx-_pan.x)*(nz/_zoom); _pan.y=my-(my-_pan.y)*(nz/_zoom);
  _zoom=nz; _render();
}

function _center() {
  const list=Object.values(_hexes);
  if(!list.length){_pan={x:400,y:280};_zoom=1;return;}
  const px=list.map(h=>hexToPixel(h.q,h.r).x);
  const py=list.map(h=>hexToPixel(h.q,h.r).y);
  const cx=(Math.min(...px)+Math.max(...px))/2;
  const cy=(Math.min(...py)+Math.max(...py))/2;
  _pan={x:450-cx,y:300-cy}; _zoom=1;
}

// ── Init ──────────────────────────────────────────────────────────────────────

export async function init(container) {
  _container=container; _hexes={}; _teleports=[]; _selectedHex=null;
  _zoom=1; _pan={x:400,y:280}; _drawingTeleport=null;

  container.innerHTML=`
    <div class="wb-layout">
      <div class="wb-sidebar">
        <div style="font-size:0.72rem;font-weight:700;color:var(--text-muted);letter-spacing:0.1em;padding:8px 10px">
          TERRAIN
        </div>
        <div class="wb-palette"></div>
        <div style="font-size:0.7rem;color:var(--text-muted);padding:8px 10px;line-height:1.6">
          Kliknij puste → maluj<br>
          Kliknij hex → edytuj<br>
          Alt+drag → przesuń<br>
          Scroll → zoom
        </div>
        <div id="wb-zoom-label" style="font-size:0.7rem;color:var(--text-muted);padding:4px 10px">Zoom: 100%</div>
        <button class="secondary-btn" id="wb-center" style="margin:6px 10px;font-size:0.72rem;width:calc(100% - 20px)">⊡ Dopasuj widok</button>
      </div>
      <div class="wb-canvas-wrap">
        <svg id="wb-svg" style="width:100%;height:100%;background:#080608;display:block"></svg>
      </div>
      <div class="wb-detail">
        <div style="color:var(--text-muted);padding:12px;font-size:0.82rem">Kliknij hex aby edytować.</div>
      </div>
    </div>`;

  _svg=container.querySelector("#wb-svg");

  try { await _load(); } catch(e) {
    container.innerHTML=`<p style="color:var(--accent-red);padding:20px">Błąd ładowania mapy: ${e.message}</p>`;
    return;
  }

  _renderPalette(); _center(); _render();

  _svg.addEventListener("wheel",_onWheel,{passive:false});
  let _ds=null;
  _svg.addEventListener("mousedown",e=>{
    if(e.button===1||(e.button===0&&e.altKey)){
      _ds={x:e.clientX-_pan.x,y:e.clientY-_pan.y};e.preventDefault();
    }
  });
  window.addEventListener("mousemove",e=>{
    if(_ds){_pan={x:e.clientX-_ds.x,y:e.clientY-_ds.y};_render();}
  });
  window.addEventListener("mouseup",()=>{_ds=null;});
  container.querySelector("#wb-center").onclick=()=>{_center();_render();};
}
