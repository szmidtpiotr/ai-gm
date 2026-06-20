// FADM-P11 (#413) — sekcja "System" sportowana 1:1 z admin_panel_v3 monolitu.
// 12 zakładek (stab): LLM, Baza, Konfiguracja, Slash, Wskrzeszenie, Email, Wygląd,
// Teksty, Głos, Narracja, Tryby gry, Obrazy. Lazy-load per zakładka (_sysTabLoaded).
import { apiFetch, ADMIN_TOKEN_KEY } from '../shared/api.js';
import { showToast } from '../shared/toast.js';

const _esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

// ── Module-level state (wyciągnięte z IIFE monolitu) ──────────────────────────
let _voiceConfig = null;
let _sysLlmData = null;
let _sysConfigParsed = null;
let _sysConfigWarnings = [];
const _sysTabLoaded = new Set();
let _igModels = [];
let _txtData = [];
let _vtestRec = null, _vtestWs = null;

const _WHISPER_PRESETS = [
  { model:'tiny',     size:'39 MB',  vram:'~200 MB',  desc:'najszybszy' },
  { model:'base',     size:'74 MB',  vram:'~400 MB',  desc:'szybki' },
  { model:'small',    size:'244 MB', vram:'~600 MB',  desc:'zbalansowany' },
  { model:'medium',   size:'769 MB', vram:'~1.5 GB',  desc:'dobry PL' },
  { model:'large-v2', size:'1.5 GB', vram:'~3 GB',    desc:'świetny' },
  { model:'large-v3', size:'1.5 GB', vram:'~3 GB',    desc:'najlepszy PL ★' },
];

const _VIS_PERIODS = [
  { key: 'rano',       label: 'Rano' },
  { key: 'popoludnie', label: 'Popołudnie' },
  { key: 'wieczor',    label: 'Wieczór' },
  { key: 'noc',        label: 'Noc' },
];
const _VIS_SCREENS = ['login','heroes','campaigns','new-campaign','wizard','game','sheet','settings','death','victory'];

const _HTML = `
    <div id="section-system">
      <div class="section-header">
        <div>
          <div class="section-heading">System</div>
          <div class="section-sub">Konfiguracja LLM, eksport danych, diagnostyka</div>
        </div>
      </div>

      <div class="stab-bar" id="sys-stab-bar">
        <button class="stab active" data-systab="llm">LLM</button>
        <button class="stab" data-systab="database">Baza danych</button>
        <button class="stab" data-systab="config">Konfiguracja</button>
        <button class="stab" data-systab="slash">Slash Commands</button>
        <button class="stab" data-systab="resurrection">Wskrzeszenie</button>
        <button class="stab" data-systab="email">Email</button>
        <button class="stab" data-systab="visual">Wygląd</button>
        <button class="stab" data-systab="teksty">🗒 Teksty</button>
        <button class="stab" data-systab="voice">🔊 Głos</button>
        <button class="stab" data-systab="narration">📜 Narracja</button>
        <button class="stab" data-systab="gamemodes">🎮 Tryby gry</button>
        <button class="stab" data-systab="imagegen">🖼 Obrazy</button>
      </div>

      <!-- LLM tab -->
      <div class="stab-panel active" id="systab-llm">
        <div class="card" style="margin-bottom:12px">
          <div class="card-header">
            <span class="card-title">Aktywna konfiguracja LLM</span>
            <button class="btn btn-sm btn-secondary" onclick="sysUseEnv(this)">Użyj zmiennych env</button>
          </div>
          <div id="sys-active-llm" class="info-grid" style="padding:12px 0 4px"></div>
        </div>
        <div class="card">
          <div class="card-header">
            <span class="card-title">Presety LLM</span>
            <button class="btn btn-sm btn-primary" onclick="openPresetModal(null)">+ Nowy preset</button>
          </div>
          <div class="preset-grid" id="sys-preset-grid"></div>
        </div>
      </div>

      <!-- Database tab -->
      <div class="stab-panel" id="systab-database" style="display:none">
        <div class="two-col">
          <div class="card">
            <div class="card-header">
              <span class="card-title">Informacje o bazie</span>
              <button class="btn btn-sm btn-secondary" onclick="_reloadSysDb()">Odśwież</button>
            </div>
            <div id="sys-db-stats" class="info-grid" style="padding:12px 0 4px"></div>
            <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">
              <button class="btn btn-sm btn-primary" onclick="sysDbBackup(this)">⬇ Pobierz backup</button>
              <button class="btn btn-sm btn-secondary" onclick="sysDbMigrate(this)">▶ Uruchom migracje</button>
            </div>
            <div style="margin-top:14px">
              <div class="section-sub" style="margin-bottom:6px">Przywróć z pliku</div>
              <p style="font-size:0.75rem;color:var(--red,#e55);margin-bottom:6px">⚠ Zastąpi bieżącą bazę — nieodwracalne</p>
              <input type="file" id="sys-restore-file" accept=".db" style="font-size:0.8rem" />
              <button class="btn btn-sm btn-danger" id="sys-restore-btn" disabled onclick="sysDbRestore(this)" style="margin-top:6px">🔁 Przywróć</button>
            </div>
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">Tabele</span></div>
            <div id="sys-db-tables" style="max-height:480px;overflow-y:auto"></div>
          </div>
        </div>
      </div>

      <!-- Config tab -->
      <div class="stab-panel" id="systab-config" style="display:none">
        <div class="two-col">
          <div class="card">
            <div class="card-header"><span class="card-title">Eksport konfiguracji</span></div>
            <p style="font-size:0.8rem;color:var(--t3);margin-bottom:10px">Pełna migawka JSON: statystyki, umiejętności, DC, broń, wrogowie, warunki.</p>
            <button class="btn btn-sm btn-secondary" onclick="sysConfigExport(this)">⬇ Eksportuj</button>
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">Import konfiguracji</span></div>
            <p style="font-size:0.8rem;color:var(--t3);margin-bottom:8px">Zatwierdź import → auto-backup DB. Retencja: 30 dni, min 3, maks 10 plików.</p>
            <input type="file" id="sys-config-file" accept=".json" style="font-size:0.8rem;display:block;margin-bottom:8px" onchange="sysConfigFileChange()" />
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <button class="btn btn-sm btn-secondary" id="sys-dry-btn" disabled onclick="sysConfigDryRun(this)">🔍 Dry Run</button>
              <button class="btn btn-sm btn-danger" id="sys-commit-btn" disabled onclick="sysConfigCommit(this)">✅ Zatwierdź import</button>
            </div>
            <div id="sys-config-diff" style="display:none;margin-top:12px"></div>
          </div>
        </div>
      </div>

      <!-- Slash Commands tab -->
      <div class="stab-panel" id="systab-slash" style="display:none">
        <div class="card">
          <div class="card-header">
            <span class="card-title">Komendy czatu</span>
            <button class="btn btn-sm btn-primary" id="sys-slash-save" disabled onclick="sysSlashSave(this)">Zapisz komendy</button>
          </div>
          <p style="font-size:0.8rem;color:var(--t3);margin-bottom:10px">Admin = widoczna dla admina, Gracz = widoczna dla gracza. Pole opisu = podpowiedź w /help.</p>
          <div style="display:grid;grid-template-columns:140px 140px 56px 56px 1fr;gap:4px;font-size:0.75rem;color:var(--t3);font-weight:600;padding:0 4px 4px">
            <span>Komenda</span><span>Alias</span><span style="text-align:center">Admin</span><span style="text-align:center">Gracz</span><span>Opis</span>
          </div>
          <div id="sys-slash-rows"></div>
        </div>
      </div>

      <!-- Wskrzeszenie tab -->
      <div class="stab-panel" id="systab-resurrection" style="display:none">
        <div class="card">
          <div class="card-header"><span class="card-title">🪦 Konfiguracja wskrzeszania</span></div>
          <div style="padding:14px;display:flex;flex-direction:column;gap:12px;max-width:520px">
            <div style="font-size:0.78rem;color:var(--t3)"><strong>Tryb</strong> = czym gracz płaci za wskrzeszenie (koszt). <strong>Domyślny limit</strong> = ile razy może wskrzesić zmarłą postać (puste = bez limitu). Tryby: <code>admin_free</code> — za darmo; <code>gold_percent</code> — % posiadanego złota; <code>gold_recent_days</code> — złoto zarobione w ostatnich dniach; <code>xp_revert</code> — cofnięcie części XP; <code>item_loss</code> — utrata przedmiotu.</div>
            <div class="form-row" style="flex-direction:row;align-items:center;gap:10px">
              <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-weight:600">
                <input type="checkbox" id="sys-res-enabled"> Włącz wskrzeszenia (globalnie)
              </label>
              <span style="font-size:0.72rem;color:var(--t3)">(wyłączone = żaden gracz nie może wskrzesić)</span>
            </div>
            <div class="form-row"><label class="form-label">Tryb</label>
              <select class="form-input" id="sys-res-mode">
                <option value="admin_free">za darmo (admin)</option>
                <option value="gold_percent">% złota gracza</option>
                <option value="gold_recent_days">złoto z ostatnich dni</option>
                <option value="xp_revert">cofnięcie XP</option>
                <option value="item_loss">utrata przedmiotu</option>
              </select>
            </div>
            <div class="form-row"><label class="form-label">Domyślny limit (default_uses)</label>
              <input class="form-input" id="sys-res-default" type="number" min="0" placeholder="3">
            </div>
            <div class="form-row"><label class="form-label">cap_percent (dla percent_of_xp, 0–100)</label>
              <input class="form-input" id="sys-res-cap" type="number" min="0" max="100" placeholder="50">
            </div>
            <div class="form-row"><label class="form-label">Wartość (value, opcjonalna)</label>
              <input class="form-input" id="sys-res-value" type="number" placeholder="—">
            </div>
            <div><button class="btn btn-primary" id="sys-res-save">Zapisz</button></div>
          </div>
        </div>
      </div>

      <!-- Email tab -->
      <div class="stab-panel" id="systab-email" style="display:none">
        <div class="two-col">
          <div class="card">
            <div class="card-header"><span class="card-title">SMTP</span></div>
            <div style="display:flex;flex-direction:column;gap:10px" id="sys-email-form">
              <div class="form-row"><label>Host SMTP</label><input id="em-host" class="field-input form-mono" placeholder="smtp.gmail.com" /></div>
              <div class="form-row"><label>Port</label><input id="em-port" class="field-input" type="number" value="587" style="width:100px" /></div>
              <div class="form-row" style="flex-direction:row;align-items:center;gap:10px">
                <label><input type="checkbox" id="em-tls" checked /> TLS/STARTTLS</label>
              </div>
              <div class="form-row"><label>Użytkownik</label><input id="em-user" class="field-input form-mono" /></div>
              <div class="form-row"><label>Hasło</label><input id="em-pass" class="field-input form-mono" type="password" placeholder="(zostaw puste, by nie zmieniać)" /></div>
              <div class="form-row"><label>Adres From</label><input id="em-from-addr" class="field-input form-mono" placeholder="noreply@example.com" /></div>
              <div class="form-row"><label>Nazwa From</label><input id="em-from-name" class="field-input" placeholder="AI-GM" /></div>
              <button class="btn btn-primary btn-sm" onclick="sysEmailSave(this)" style="align-self:flex-start">Zapisz SMTP</button>
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:12px">
            <div class="card">
              <div class="card-header"><span class="card-title">Test e-mail</span></div>
              <div class="form-row"><label>Adres testowy</label><input id="em-test-addr" class="field-input form-mono" placeholder="test@example.com" /></div>
              <button class="btn btn-sm btn-secondary" onclick="sysEmailTest(this)" style="margin-top:8px">Wyślij test</button>
            </div>
            <div class="card">
              <div class="card-header"><span class="card-title">Rejestracja</span></div>
              <div style="display:flex;flex-direction:column;gap:10px">
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                  <input type="checkbox" id="em-reg-open" /> Otwarta rejestracja (bez zaproszenia)
                </label>
                <button class="btn btn-sm btn-primary" onclick="sysEmailSaveReg(this)">Zapisz ustawienie</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Visual tab -->
      <div class="stab-panel" id="systab-visual" style="display:none">
        <div class="two-col">
          <div class="card">
            <div class="card-header">
              <span class="card-title">Pora dnia</span>
              <label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;cursor:pointer">
                <input type="checkbox" id="vis-tod-enabled" onchange="visSaveSetting('time_of_day.enabled',this.checked)" /> Włączona
              </label>
            </div>
            <div class="form-row" style="margin-bottom:12px">
              <label>Tryb</label>
              <select id="vis-tod-mode" class="field-input" style="width:180px" onchange="visSaveSetting('time_of_day.mode',this.value)">
                <option value="bg">Tło (bg)</option>
                <option value="frame">Ramka (frame)</option>
                <option value="both">Oba (both)</option>
                <option value="off">Wyłączony</option>
              </select>
            </div>
            <div id="vis-periods" style="display:grid;grid-template-columns:1fr 1fr;gap:10px"></div>
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">Tła ekranów</span></div>
            <div id="vis-bg-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:10px"></div>
          </div>
        </div>
      </div>

      <!-- Teksty stab — UI text CMS -->
      <div class="stab-panel" id="systab-teksty" style="display:none">
        <div class="card" style="margin-bottom:14px">
          <div class="card-header">
            <span class="card-title">Teksty UI</span>
            <div style="display:flex;gap:8px;align-items:center">
              <select id="txt-screen-filter" class="field-input" style="width:160px;font-size:0.82rem" onchange="_loadSysTeksty()">
                <option value="">Wszystkie ekrany</option>
                <option value="login">Logowanie</option>
                <option value="heroes">Bohaterowie</option>
                <option value="campaigns">Kampanie</option>
                <option value="game">Gra</option>
                <option value="onboarding">Onboarding</option>
              </select>
              <span class="badge badge-slate" id="txt-count-badge">—</span>
            </div>
          </div>
          <div id="txt-list" style="display:flex;flex-direction:column;gap:10px;padding:4px 0"></div>
        </div>
      </div>
      <!-- Voice stab — Piper TTS · Whisper STT -->
      <div class="stab-panel" id="systab-voice" style="display:none">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
          <div>
            <span style="font-weight:600;font-size:0.95rem">TTS · Whisper STT</span>
            <span style="font-size:0.78rem;color:var(--t3);margin-left:8px">Serwer głosu AI-GM</span>
          </div>
          <div id="voice-status-badge"><span class="badge badge-slate">Sprawdzanie…</span></div>
        </div>

        <!-- Host management -->
        <div class="card" style="margin-bottom:14px">
          <div class="card-header"><span class="card-title">🖥 Serwer głosu</span><span class="card-count" id="voice-active-label">—</span></div>
          <div id="voice-hosts-list" style="padding:12px 14px;display:flex;flex-direction:column;gap:8px">
            <div style="color:var(--t3);font-size:0.82rem">Ładowanie hostów…</div>
          </div>
          <div style="padding:12px 14px;border-top:1px solid var(--border);display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap">
            <div style="flex:1;min-width:200px"><label class="form-label">Dodaj host (URL)</label><input class="form-input" id="vh-url" placeholder="http://192.168.1.x:8300"></div>
            <div style="width:150px"><label class="form-label">Etykieta</label><input class="form-input" id="vh-label" placeholder="Nazwa"></div>
            <div style="width:90px"><label class="form-label">Typ</label><select class="form-input" id="vh-kind"><option value="cpu">CPU</option><option value="gpu">GPU</option></select></div>
            <button class="btn btn-secondary btn-sm" onclick="addVoiceHost(this)">+ Dodaj</button>
          </div>
        </div>

        <!-- TTS + STT config (editable) -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
          <div class="card">
            <div class="card-header"><span class="card-title">TTS — Synteza mowy</span><span id="v-tts-enabled"></span></div>
            <div style="padding:12px 16px;display:flex;flex-direction:column;gap:14px">

              <!-- Voice -->
              <div>
                <div class="form-row"><label class="form-label">Głos</label><select class="form-input" id="v-voice-select"></select></div>
              </div>

              <!-- Speed -->
              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                  <label class="form-label" style="margin:0">Prędkość mowy</label>
                  <strong style="font-size:0.85rem;color:var(--accent)" id="v-tts-speed-val">1.0</strong>
                </div>
                <input type="range" id="v-tts-speed-input" min="0.5" max="2.0" step="0.05" value="1.0" style="width:100%" oninput="document.getElementById('v-tts-speed-val').textContent=parseFloat(this.value).toFixed(2)">
                <div style="font-size:0.7rem;color:var(--t3);margin-top:3px">Tempo wymowy. 1.0 = naturalne, 0.8 = wolniej, 1.3 = szybciej.</div>
              </div>

              <!-- Noise scale (Piper) -->
              <div style="opacity:0.6">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                  <label class="form-label" style="margin:0;color:var(--t3)">Noise scale <span style="font-size:0.68rem">(tylko Piper)</span></label>
                  <strong style="font-size:0.85rem;color:var(--t3)" id="v-tts-noise-val">0.67</strong>
                </div>
                <input type="range" id="v-tts-noise-input" min="0" max="1" step="0.01" value="0.667" style="width:100%" oninput="document.getElementById('v-tts-noise-val').textContent=parseFloat(this.value).toFixed(2)">
                <div style="font-size:0.7rem;color:var(--t3);margin-top:3px">Wariancja głosu Piper. Wyższa = bardziej zróżnicowana intonacja.</div>
              </div>

              <div style="border-top:1px solid var(--border);padding-top:4px;font-size:0.72rem;color:var(--accent);font-weight:600;letter-spacing:0.03em">⚙ F5-TTS</div>

              <!-- NFE steps -->
              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                  <label class="form-label" style="margin:0">Kroki dyfuzji (NFE)</label>
                  <strong style="font-size:0.85rem;color:var(--accent)" id="v-tts-nfe-val">32</strong>
                </div>
                <input type="range" id="v-tts-nfe-input" min="4" max="64" step="1" value="32" style="width:100%" oninput="document.getElementById('v-tts-nfe-val').textContent=this.value">
                <div style="font-size:0.7rem;color:var(--t3);margin-top:3px">Liczba kroków modelu dyfuzji. 16 = szybciej, 32 = balans, 64 = najlepsza jakość (ale wolniej).</div>
              </div>

              <!-- CFG strength -->
              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                  <label class="form-label" style="margin:0">Wierność głosu (CFG)</label>
                  <strong style="font-size:0.85rem;color:var(--accent)" id="v-tts-cfg-val">2.0</strong>
                </div>
                <input type="range" id="v-tts-cfg-input" min="0" max="5" step="0.1" value="2.0" style="width:100%" oninput="document.getElementById('v-tts-cfg-val').textContent=parseFloat(this.value).toFixed(1)">
                <div style="font-size:0.7rem;color:var(--t3);margin-top:3px">Siła dopasowania do referencyjnego głosu. Zalecane 1.5–2.5. Zbyt wysoka wartość może powodować artefakty.</div>
              </div>

              <!-- Cross-fade duration -->
              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                  <label class="form-label" style="margin:0">Cross-fade segmentów</label>
                  <strong style="font-size:0.85rem;color:var(--accent)" id="v-tts-crossfade-val">0.15</strong>
                </div>
                <input type="range" id="v-tts-crossfade-input" min="0" max="1" step="0.01" value="0.15" style="width:100%" oninput="document.getElementById('v-tts-crossfade-val').textContent=parseFloat(this.value).toFixed(2)">
                <div style="font-size:0.7rem;color:var(--t3);margin-top:3px">Długość wygładzenia przejścia między segmentami długiego tekstu (sekundy). 0 = bez wygładzenia.</div>
              </div>

              <!-- Sway sampling coef -->
              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                  <label class="form-label" style="margin:0">Sway sampling</label>
                  <strong style="font-size:0.85rem;color:var(--accent)" id="v-tts-sway-val">-1.0</strong>
                </div>
                <input type="range" id="v-tts-sway-input" min="-1" max="1" step="0.05" value="-1" style="width:100%" oninput="document.getElementById('v-tts-sway-val').textContent=parseFloat(this.value).toFixed(2)">
                <div style="font-size:0.7rem;color:var(--t3);margin-top:3px">Eksperymentalny sampler. -1 = wyłączony (domyślnie). Dodatnie wartości mogą poprawić jakość przy niskim NFE.</div>
              </div>

              <!-- Seed -->
              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                  <label class="form-label" style="margin:0">Seed</label>
                  <label style="display:flex;gap:6px;align-items:center;font-size:0.75rem;color:var(--t3)"><input type="checkbox" id="v-tts-seed-random" checked onchange="_onSeedRandomToggle()"> losowy</label>
                </div>
                <input class="form-input" type="number" id="v-tts-seed-input" value="-1" min="-1" style="width:120px" disabled>
                <div style="font-size:0.7rem;color:var(--t3);margin-top:3px">-1 = losowy wynik przy każdym wywołaniu. Stała liczba daje powtarzalne audio (przydatne do testów).</div>
              </div>

              <div style="display:flex;gap:8px;align-items:center;margin-top:2px">
                <button class="btn btn-primary btn-sm" onclick="saveTTSConfig(this)">Zapisz TTS</button>
                <button class="btn btn-sm btn-secondary" id="v-tts-toggle-btn" onclick="toggleVoiceTTS()">Włącz / Wyłącz</button>
              </div>
            </div>
          </div>
          <div class="card">
            <div class="card-header"><span class="card-title">STT — Rozpoznawanie mowy</span><span id="v-stt-enabled"></span></div>
            <div style="padding:12px 16px;display:flex;flex-direction:column;gap:10px">
              <div>
                <label class="form-label" style="margin-bottom:6px">Model Whisper</label>
                <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:5px" id="whisper-preset-grid"></div>
              </div>
              <div class="form-row"><label class="form-label">Model (ręcznie)</label>
                <select class="form-input" id="v-stt-model-select">
                  <option value="tiny">tiny</option>
                  <option value="base">base</option>
                  <option value="small">small</option>
                  <option value="medium">medium</option>
                  <option value="large-v2">large-v2</option>
                  <option value="large-v3">large-v3</option>
                </select>
              </div>
              <div class="form-row"><label class="form-label">Język (ISO)</label><input class="form-input" type="text" id="v-stt-lang-input" maxlength="5" placeholder="pl" style="width:80px"></div>
              <div class="form-row"><label class="form-label">Beam size</label><input class="form-input" type="number" id="v-stt-beam-input" min="1" max="10" style="width:80px"></div>
              <div class="form-row"><label class="form-label">VAD filter</label><label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="v-stt-vad-check"> Włącz</label></div>
              <div class="form-row"><label class="form-label">Auto-stop ms</label><input class="form-input" type="number" id="v-stt-silence-input" min="500" max="10000" step="100" style="width:100px"></div>
              <div style="display:flex;gap:8px;align-items:center;margin-top:4px">
                <button class="btn btn-primary btn-sm" onclick="saveSTTConfig(this)">Zapisz STT</button>
                <button class="btn btn-sm btn-secondary" id="v-stt-toggle-btn" onclick="toggleVoiceSTT()">Włącz / Wyłącz</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Test console -->
        <div class="card" style="margin-top:14px">
          <div class="card-header"><span class="card-title">🎙 Konsola testowa</span><span class="card-count">aktywny host</span></div>
          <div style="padding:14px;display:grid;grid-template-columns:1fr 1fr;gap:16px">
            <div>
              <label class="form-label">Test TTS — synteza</label>
              <div style="display:flex;gap:8px">
                <input class="form-input" id="vtest-text" value="Witaj w świecie przygody, bohaterze." style="flex:1">
                <button class="btn btn-primary btn-sm" id="vtest-tts-btn" onclick="testTTS(this)">▶ Odtwórz</button>
              </div>
              <div style="font-size:0.72rem;color:var(--t3);margin-top:6px" id="vtest-tts-status">Odtwarza WAV z aktywnego hosta.</div>
            </div>
            <div>
              <label class="form-label">Test STT — mikrofon (4 s)</label>
              <div style="display:flex;gap:8px;align-items:center">
                <button class="btn btn-secondary btn-sm" id="vtest-stt-btn" onclick="testSTT(this)">● Nagraj 4 s</button>
                <span id="vtest-stt-out" style="font-size:0.8rem;color:var(--t2);flex:1">—</span>
              </div>
              <div style="font-size:0.72rem;color:var(--t3);margin-top:6px">Nagrywa z mikrofonu i transkrybuje przez aktywny host.</div>
            </div>
          </div>
        </div>

        <!-- Per-route TTS toggles -->
        <div class="card" style="margin-top:14px">
          <div class="card-header"><span class="card-title">TTS per-route (klient)</span><span class="card-count">preferencje przeglądarki</span></div>
          <div style="padding:14px;font-size:0.78rem;color:var(--t3);margin-bottom:6px">Wyłącz wymowę dla wybranych typów wiadomości w UI gracza. Ustawienia zapisywane w localStorage tej przeglądarki.</div>
          <div style="padding:0 14px 14px;display:grid;grid-template-columns:1fr 1fr;gap:8px" id="v-route-toggles">
            <label style="display:flex;gap:8px;align-items:center;cursor:pointer;padding:8px;border:1px solid var(--border);border-radius:6px"><input type="checkbox" data-vroute="narration"> Narracja GM</label>
            <label style="display:flex;gap:8px;align-items:center;cursor:pointer;padding:8px;border:1px solid var(--border);border-radius:6px"><input type="checkbox" data-vroute="mem"> /mem (wspomnienia)</label>
            <label style="display:flex;gap:8px;align-items:center;cursor:pointer;padding:8px;border:1px solid var(--border);border-radius:6px"><input type="checkbox" data-vroute="helpme"> /helpme (pomoc)</label>
            <label style="display:flex;gap:8px;align-items:center;cursor:pointer;padding:8px;border:1px solid var(--border);border-radius:6px"><input type="checkbox" data-vroute="skill"> Rzuty skill</label>
            <label style="display:flex;gap:8px;align-items:center;cursor:pointer;padding:8px;border:1px solid var(--border);border-radius:6px"><input type="checkbox" data-vroute="combat"> Mechanika walki</label>
          </div>
        </div>
      </div>

      <!-- Narration tab -->
      <div class="stab-panel" id="systab-narration" style="display:none">
        <div class="narration-grid">
          <div class="card">
            <div class="card-header">
              <span class="card-title">System prompt GM</span>
              <button class="btn btn-sm btn-secondary" id="prompt-edit-btn" onclick="togglePromptEdit()">✎ Edytuj</button>
            </div>
            <textarea class="prompt-textarea" id="prompt-textarea" disabled rows="24" style="width:100%;box-sizing:border-box;resize:vertical;min-height:360px"></textarea>
          </div>
          <div style="display:flex;flex-direction:column;gap:16px">
            <div class="card">
              <div class="card-header"><span class="card-title">Ton narracji</span></div>
              <div style="padding:14px;display:flex;flex-direction:column;gap:10px">
                <div style="display:flex;gap:8px">
                  <button class="tone-btn btn btn-sm btn-secondary" onclick="setTone(this)">Formalny</button>
                  <button class="tone-btn btn btn-sm btn-secondary active" onclick="setTone(this)">Zrównoważony</button>
                  <button class="tone-btn btn btn-sm btn-secondary" onclick="setTone(this)">Dramatyczny</button>
                </div>
                <div id="tone-desc" style="font-size:0.78rem;color:var(--t3);line-height:1.5">Zrównoważony: narracja zachowuje powagę sytuacji bez przesadnego dramatyzmu.</div>
              </div>
            </div>

            <!-- E9 (#424) — Story Gravity config -->
            <div class="card">
              <div class="card-header"><span class="card-title">⚖ Story Gravity</span></div>
              <div style="padding:14px;display:flex;flex-direction:column;gap:10px">
                <div style="font-size:0.78rem;color:var(--t3);line-height:1.5">Gdy wymagany beat fabularny nie odpali przez N tur, narrator dostaje rosnącą presję: L1 podpowiedź, L2 instrukcja, L3 wymuszona scena (domyślnie wyłączona).</div>
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-weight:600"><input type="checkbox" id="sys-sg-enabled"> Włączone (globalnie)</label>
                <div class="form-row"><label class="form-label">L1 — podpowiedź po (turach)</label><input class="form-input" id="sys-sg-l1" type="number" min="1" max="200" placeholder="5"></div>
                <div class="form-row"><label class="form-label">L2 — instrukcja po (turach)</label><input class="form-input" id="sys-sg-l2" type="number" min="1" max="200" placeholder="10"></div>
                <div class="form-row"><label class="form-label">L3 — wymuszona scena po (turach)</label><input class="form-input" id="sys-sg-l3" type="number" min="1" max="200" placeholder="15"></div>
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer"><input type="checkbox" id="sys-sg-l3-enabled"> L3 aktywne dla Nowej Kampanii <span style="font-size:0.72rem;color:var(--t3)">(domyślnie OFF — wolna eksploracja)</span></label>
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;margin-top:4px"><input type="checkbox" id="sys-sg-l3-enabled-gotowa" checked> L3 aktywne dla Gotowej Kampanii <span style="font-size:0.72rem;color:var(--t3)">(domyślnie ON — gracz wybrał historię)</span></label>
                <div><button class="btn btn-primary" id="sys-sg-save">Zapisz progi</button></div>
              </div>
            </div>
          </div>

          <!-- Combat narrative toggle -->
          <div class="card">
            <div class="card-header"><span class="card-title">⚔ Narracja w walce</span></div>
            <div style="padding:14px;display:flex;flex-direction:column;gap:10px">
              <div style="font-size:0.78rem;color:var(--t3);line-height:1.5">Globalny przełącznik — wyłącza generowanie narracji LLM po każdej akcji bojowej. Gracz widzi tylko mechaniczny wynik (Cios trafia — X obrażeń). Każdy gracz może też wyłączyć narrację indywidualnie w swoich ustawieniach.</div>
              <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-weight:600">
                <input type="checkbox" id="sys-skip-combat-narr"> Wyłącz narrację bojową globalnie (szybka walka)
              </label>
              <div><button class="btn btn-primary" id="sys-skip-combat-narr-save">Zapisz</button></div>
            </div>
          </div>
        </div>
        </div>
      </div>

      <!-- Game modes tab -->
      <div class="stab-panel" id="systab-gamemodes" style="display:none">
        <div class="card">
          <div class="card-header">
            <span class="card-title">Tryby gry</span>
            <button class="btn btn-sm btn-primary" onclick="saveGameModes()">Zapisz</button>
          </div>
          <div style="padding:14px;display:flex;flex-direction:column;gap:18px">
            <p style="color:var(--t3);font-size:0.82rem;margin:0">Włącz lub wyłącz tryby dostępne dla graczy na ekranie kampanii.</p>

            <label style="display:flex;align-items:center;gap:12px;cursor:pointer">
              <input type="checkbox" id="gm-ai-campaign" style="width:18px;height:18px;accent-color:var(--accent)">
              <span>
                <strong style="font-size:0.92rem">Kampania AI</strong>
                <span style="display:block;font-size:0.78rem;color:var(--t3)">Gracz opisuje pomysł, AI generuje kampanię na żywo.</span>
              </span>
            </label>

            <label style="display:flex;align-items:center;gap:12px;cursor:pointer">
              <input type="checkbox" id="gm-prebuilt" style="width:18px;height:18px;accent-color:var(--accent)">
              <span>
                <strong style="font-size:0.92rem">Gotowa kampania</strong>
                <span style="display:block;font-size:0.78rem;color:var(--t3)">Gracz wybiera z predefiniowanych szablonów przygód.</span>
              </span>
            </label>

            <label style="display:flex;align-items:center;gap:12px;cursor:pointer">
              <input type="checkbox" id="gm-dungeon" style="width:18px;height:18px;accent-color:var(--accent)">
              <span>
                <strong style="font-size:0.92rem">Loch (Dungeon Kafelkowy)</strong>
                <span style="display:block;font-size:0.78rem;color:var(--t3)">Farmowalne lochy z kafelkową mapą, wrogami, zagadkami i skrzyniami.</span>
              </span>
            </label>

            <label style="display:flex;align-items:center;gap:12px;cursor:pointer">
              <input type="checkbox" id="gm-multiplayer" style="width:18px;height:18px;accent-color:var(--accent)">
              <span>
                <strong style="font-size:0.92rem">Multiplayer (Wyprawa grupowa)</strong>
                <span style="display:block;font-size:0.78rem;color:var(--t3)">Lobby wieloosobowe — gracz może tworzyć i dołączać do grupowych sesji.</span>
              </span>
            </label>
          </div>
        </div>
      </div>

      <!-- Image Gen tab -->
      <div class="stab-panel" id="systab-imagegen" style="display:none">
        <div class="card" style="margin-bottom:12px">
          <div class="card-header">
            <span class="card-title">Serwis generowania obrazów</span>
            <button class="btn btn-sm btn-secondary" onclick="_pingImageGen()">⚡ Ping</button>
          </div>
          <div style="padding:12px 0 4px">
            <div id="imagegen-status" style="font-size:0.8rem;color:var(--t3);margin-bottom:10px">Sprawdź status połączenia.</div>
            <div class="form-row" style="margin-bottom:8px">
              <label class="form-label">URL serwisu (ComfyUI / Flask)</label>
              <input class="form-input" id="ig-url" type="text" placeholder="http://192.168.1.170:8765">
            </div>
            <div class="form-row" style="margin-bottom:8px">
              <label class="form-label" style="display:flex;align-items:center;gap:8px">
                Checkpoint / model
                <button type="button" class="btn btn-sm btn-secondary" style="font-size:0.72rem;padding:2px 8px" onclick="_refreshImageGenModels()">↺ Odśwież</button>
              </label>
              <select class="form-input" id="ig-checkpoint">
                <option value="">(domyślny serwisu)</option>
              </select>
              <div id="ig-model-hint" style="font-size:0.72rem;color:var(--t3);margin-top:3px"></div>
            </div>
          </div>
        </div>
        <div class="card" style="margin-bottom:12px">
          <div class="card-header"><span class="card-title">Domyślne parametry generowania</span></div>
          <div style="padding:12px 0 4px;display:flex;gap:24px;flex-wrap:wrap">
            <div class="form-row">
              <label class="form-label">Kroki (generate)</label>
              <input class="form-input" id="ig-steps" type="number" min="1" max="50" style="width:80px">
            </div>
            <div class="form-row">
              <label class="form-label">Kroki (refine)</label>
              <input class="form-input" id="ig-refine-steps" type="number" min="1" max="50" style="width:80px">
            </div>
            <div class="form-row">
              <label class="form-label">Rozmiar portretu (wrogowie/NPC)</label>
              <select class="form-input" id="ig-portrait-size" style="width:200px">
                <option value="576x1024">576×1024 portret ★</option>
                <option value="768x1024">768×1024 portret 3:4</option>
                <option value="512x512">512×512</option>
                <option value="768x768">768×768</option>
              </select>
            </div>
          </div>
        </div>
        <div class="card" style="margin-bottom:12px">
          <div class="card-header"><span class="card-title">Galeria — statystyki</span></div>
          <div id="imagegen-gallery-stats" style="padding:12px;font-size:0.85rem;color:var(--t2)">Ładowanie…</div>
        </div>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:4px">
          <button class="btn btn-primary" id="ig-save-btn">💾 Zapisz ustawienia</button>
        </div>
      </div>
    </div>`;

// ── Tab wiring + lazy load ────────────────────────────────────────────────────
function _wireSysTabs() {
  const bar = document.getElementById('sys-stab-bar');
  if (!bar) return;
  bar.querySelectorAll('.stab[data-systab]').forEach(btn => {
    btn.addEventListener('click', () => {
      bar.querySelectorAll('.stab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.systab;
      document.querySelectorAll('#section-system .stab-panel').forEach(p => p.style.display = 'none');
      const p = document.getElementById(`systab-${tab}`);
      if (p) { p.style.display = ''; p.classList.add('active'); }
      _loadSysTab(tab);
    });
  });
}

function _loadSysTab(tab) {
  if (_sysTabLoaded.has(tab)) return;
  _sysTabLoaded.add(tab);
  const fn = {
    llm: _loadSysLlm, database: _loadSysDatabase, config: () => Promise.resolve(),
    slash: _loadSysSlash, email: _loadSysEmail, visual: _loadSysVisual,
    resurrection: _loadSysResurrection, teksty: _loadSysTeksty, voice: _loadVoice,
    narration: _loadNarration, gamemodes: _loadGameModes, imagegen: _loadSysImageGen,
  }[tab];
  if (fn) fn().catch(e => { _sysTabLoaded.delete(tab); console.warn('sys tab', tab, e.message); });
}

// ── LLM tab ───────────────────────────────────────────────────────────────────
async function _loadSysLlm() {
  _sysTabLoaded.add('llm');
  try {
    const d = await apiFetch('/api/admin/llm/global-settings');
    _sysLlmData = d;
    const presets = d.presets || [];
    const activeId = d.active_preset_id ?? null;
    const active = presets.find(p => p.id === activeId);

    const pill = document.getElementById('topbar-llm-pill');
    if (pill && active) pill.textContent = `⚡ ${active.label || active.provider || '—'}`;

    const activBox = document.getElementById('sys-active-llm');
    if (activBox) {
      const s = d.settings || {};
      const effModel = active?.model || s.model || '—';
      const effProvider = active?.provider || s.provider || '—';
      const effUrl = active?.base_url || s.base_url || '—';
      activBox.innerHTML = [
        ['Preset', active ? _esc(active.label) : '<em style="color:var(--t3)">zmienne środowiskowe</em>'],
        ['Dostawca', _esc(effProvider)],
        ['Model', `<span class="td-mono">${_esc(effModel)}</span>`],
        ['URL', `<span class="td-mono" style="word-break:break-all">${_esc(effUrl)}</span>`],
      ].map(([k,v]) => `<div class="info-row"><span class="info-key">${k}</span><span class="info-val">${v}</span></div>`).join('');
    }

    const grid = document.getElementById('sys-preset-grid');
    if (grid) {
      if (!presets.length) {
        grid.innerHTML = `<div style="padding:16px;color:var(--t3);font-size:0.85rem">Brak presetów — używane zmienne środowiskowe.</div>`;
      } else {
        grid.innerHTML = presets.map(p => {
          const isActive = p.id === activeId;
          return `<div class="preset-card${isActive ? ' active' : ''}">
            <div class="preset-card-top">
              <span class="preset-dot${isActive ? ' active' : ''}"></span>
              <span class="preset-name">${_esc(p.label || p.provider || '—')}</span>
              <span class="preset-provider">${_esc(p.provider || '—')}</span>
            </div>
            <div class="preset-model">${_esc(p.model || '—')}</div>
            <div class="preset-row"><span>Temperatura</span><span class="preset-val">${p.temperature ?? '—'}</span></div>
            <div class="preset-row"><span>Max tokens</span><span class="preset-val">${p.max_tokens ?? '—'}</span></div>
            <div class="preset-row" style="margin-top:8px;flex-wrap:wrap;gap:4px">
              ${isActive
                ? `<span class="badge badge-green" style="font-size:0.68rem">● Aktywny</span>`
                : `<button class="btn btn-sm btn-primary" style="padding:2px 8px;font-size:0.72rem" onclick="activatePreset(${p.id},this)">Aktywuj</button>`}
              <button class="btn btn-sm btn-secondary" style="padding:2px 8px;font-size:0.72rem" onclick="openPresetModal(${p.id})">Edytuj</button>
              ${!isActive ? `<button class="btn btn-sm btn-danger" style="padding:2px 8px;font-size:0.72rem" onclick="deletePreset(${p.id},this)">Usuń</button>` : ''}
            </div>
          </div>`;
        }).join('');
      }
    }
  } catch(e) {
    console.warn('_loadSysLlm', e.message);
    const grid = document.getElementById('sys-preset-grid');
    if (grid) grid.innerHTML = `<div style="padding:16px;color:var(--red,#e55)">${_esc(e.message)}</div>`;
  }
}

async function activatePreset(presetId, btn) {
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
  try {
    await apiFetch(`/api/admin/llm/presets/${presetId}/activate`, { method: 'POST' });
    _sysTabLoaded.delete('llm');
    await _loadSysLlm();
    showToast('Preset aktywowany.', 'success');
  } catch(e) {
    showToast(e.message || 'Błąd aktywacji.', 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'Aktywuj'; }
  }
}

async function deletePreset(presetId, btn) {
  if (!confirm('Usunąć preset LLM?')) return;
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
  try {
    await apiFetch(`/api/admin/llm/presets/${presetId}`, { method: 'DELETE' });
    _sysTabLoaded.delete('llm');
    await _loadSysLlm();
    showToast('Preset usunięty.', 'success');
  } catch(e) {
    showToast(e.message || 'Błąd usuwania.', 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'Usuń'; }
  }
}

async function sysUseEnv(btn) {
  if (!confirm('Wyczyścić aktywny preset i używać zmiennych środowiskowych?')) return;
  btn.disabled = true;
  try {
    await apiFetch('/api/admin/llm/use-env', { method: 'POST' });
    _sysTabLoaded.delete('llm');
    await _loadSysLlm();
    showToast('Używane zmienne środowiskowe.', 'success');
  } catch(e) {
    showToast(e.message || 'Błąd.', 'error');
  } finally { btn.disabled = false; }
}

function openPresetModal(presetId) {
  const prefill = presetId && _sysLlmData
    ? (_sysLlmData.presets || []).find(p => p.id === presetId) || {}
    : {};
  const isEdit = !!prefill.id;
  const PROVIDERS = [
    { value: 'openai', label: 'OpenAI' },
    { value: 'azure', label: 'Azure OpenAI' },
    { value: 'ollama', label: 'Ollama' },
    { value: 'other', label: 'Inny (OpenAI-compatible)' },
  ];
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.innerHTML = `<div class="modal-box" style="max-width:480px">
    <div class="modal-head"><span>${isEdit ? 'Edytuj preset' : 'Nowy preset LLM'}</span><button onclick="this.closest('.modal-overlay').remove()">✕</button></div>
    <div class="modal-body" style="display:flex;flex-direction:column;gap:10px">
      <div class="form-row"><label>Nazwa prestu *</label><input id="pm-label" class="field-input" value="${_esc(prefill.label||'')}" placeholder="np. GPT-4o Mini" /></div>
      <div class="form-row"><label>Dostawca *</label>
        <select id="pm-provider" class="field-input">
          ${PROVIDERS.map(p => `<option value="${p.value}"${(prefill.provider||'openai')===p.value?' selected':''}>${p.label}</option>`).join('')}
        </select>
      </div>
      <div class="form-row"><label>Model *</label>
        <div style="display:flex;gap:6px">
          <input id="pm-model" class="field-input" value="${_esc(prefill.model||'')}" placeholder="np. gpt-4o-mini" style="flex:1;min-width:0" />
          <button id="pm-fetch-btn" class="btn btn-secondary" type="button" style="white-space:nowrap;padding:4px 10px;font-size:0.8rem">↻ Pobierz</button>
        </div>
        <div id="pm-fetch-status" style="font-size:0.72rem;color:var(--t3);margin-top:3px;min-height:14px"></div>
      </div>
      <div class="form-row"><label>Base URL</label><input id="pm-base-url" class="field-input form-mono" value="${_esc(prefill.base_url||'')}" placeholder="https://api.openai.com/v1" /></div>
      <div class="form-row"><label>API Key</label><input id="pm-api-key" class="field-input form-mono" type="password" value="${_esc(prefill.api_key||'')}" placeholder="sk-…" /></div>
      <div class="form-row"><label>Temperatura</label><input id="pm-temp" class="field-input" type="number" step="0.1" min="0" max="2" value="${prefill.temperature ?? 0.8}" /></div>
      <div class="form-row"><label>Max tokens</label><input id="pm-maxtok" class="field-input" type="number" min="256" max="32000" value="${prefill.max_tokens ?? 2048}" /></div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Anuluj</button>
      <button class="btn btn-primary" onclick="savePreset(${presetId||'null'},this)">Zapisz</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);

  const _pmFetchBtn = overlay.querySelector('#pm-fetch-btn');
  const _pmFetchStatus = overlay.querySelector('#pm-fetch-status');
  _pmFetchBtn.addEventListener('click', async () => {
    const provider = overlay.querySelector('#pm-provider').value;
    const baseUrl = (overlay.querySelector('#pm-base-url').value || '').trim();
    const apiKey = (overlay.querySelector('#pm-api-key').value || '').trim() || null;
    if (!baseUrl) {
      _pmFetchStatus.textContent = 'Podaj Base URL przed pobraniem modeli.';
      _pmFetchStatus.style.color = 'var(--red)'; return;
    }
    _pmFetchBtn.disabled = true; _pmFetchBtn.textContent = '…';
    _pmFetchStatus.style.color = 'var(--t3)';
    _pmFetchStatus.textContent = provider === 'azure' ? 'Sprawdzanie wdrożonych modeli…' : 'Pobieranie listy modeli…';
    try {
      const payload = { provider, base_url: baseUrl, api_key: apiKey };
      if (isEdit && prefill.id && !apiKey) payload.preset_id = prefill.id;
      const data = await apiFetch('/api/admin/llm/fetch-models', { method: 'POST', body: JSON.stringify(payload) });
      if (!data.ok || !data.models?.length) {
        _pmFetchStatus.textContent = data.error ? `Błąd: ${data.error}` : 'Brak modeli lub nieprawidłowy klucz API.';
        _pmFetchStatus.style.color = 'var(--red)'; return;
      }
      const curModel = overlay.querySelector('#pm-model').value;
      const sel = document.createElement('select');
      sel.id = 'pm-model'; sel.className = 'field-input'; sel.style.cssText = 'flex:1;min-width:0';
      data.models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m; opt.textContent = m;
        if (m === curModel) opt.selected = true;
        sel.appendChild(opt);
      });
      overlay.querySelector('#pm-model').replaceWith(sel);
      _pmFetchStatus.textContent = `Znaleziono ${data.models.length} modeli.`;
      _pmFetchStatus.style.color = 'var(--green)';
    } catch(e) {
      _pmFetchStatus.textContent = `Błąd: ${e.message || 'nieznany'}`;
      _pmFetchStatus.style.color = 'var(--red)';
    } finally {
      _pmFetchBtn.disabled = false; _pmFetchBtn.textContent = '↻ Pobierz';
    }
  });
}

async function savePreset(presetId, btn) {
  const get = id => document.getElementById(id)?.value?.trim();
  const label = get('pm-label');
  const model = get('pm-model');
  if (!label || !model) { showToast('Wypełnij nazwę i model.', 'error'); return; }
  btn.disabled = true; btn.textContent = '⏳';
  try {
    const body = {
      preset_id: presetId || null,
      label,
      provider: get('pm-provider') || 'openai',
      model,
      base_url: get('pm-base-url') || null,
      api_key: get('pm-api-key') || null,
      temperature: parseFloat(document.getElementById('pm-temp')?.value) || 0.8,
      max_tokens: parseInt(document.getElementById('pm-maxtok')?.value) || 2048,
      activate: false,
    };
    await apiFetch('/api/admin/llm/presets', { method: 'POST', body: JSON.stringify(body) });
    btn.closest('.modal-overlay').remove();
    _sysTabLoaded.delete('llm');
    await _loadSysLlm();
    showToast('Preset zapisany.', 'success');
  } catch(e) {
    showToast(e.message || 'Błąd zapisu.', 'error');
    btn.disabled = false; btn.textContent = 'Zapisz';
  }
}

// ── Database tab ──────────────────────────────────────────────────────────────
async function _loadSysDatabase() {
  _sysTabLoaded.add('database');
  await _reloadSysDb();
  document.getElementById('sys-restore-file')?.addEventListener('change', function() {
    const btn = document.getElementById('sys-restore-btn');
    if (btn) btn.disabled = !this.files?.length;
  });
}

async function _reloadSysDb() {
  const statsEl = document.getElementById('sys-db-stats');
  const tablesEl = document.getElementById('sys-db-tables');
  if (statsEl) statsEl.innerHTML = '<div style="color:var(--t3);padding:8px">Ładowanie…</div>';
  if (tablesEl) tablesEl.innerHTML = '';
  try {
    const d = await apiFetch('/api/admin/db/info');
    const mb = (Number(d.db_size_bytes||0) / 1024 / 1024).toFixed(2);
    if (statsEl) statsEl.innerHTML = [
      ['Ścieżka', `<span class="td-mono" style="word-break:break-all">${_esc(d.db_path||'—')}</span>`],
      ['Rozmiar', `${mb} MB`],
      ['SQLite', _esc(d.sqlite_version||'—')],
    ].map(([k,v]) => `<div class="info-row"><span class="info-key">${k}</span><span class="info-val">${v}</span></div>`).join('');

    if (tablesEl) {
      const tables = [...(d.tables||[])].sort((a,b) => a.name.localeCompare(b.name));
      tablesEl.innerHTML = `<table class="data-table" style="font-size:0.8rem">
        <thead><tr><th>Tabela</th><th style="text-align:right">Wiersze</th></tr></thead>
        <tbody>${tables.map(t => `<tr>
          <td class="td-mono" style="font-size:0.75rem">${_esc(t.name)}</td>
          <td style="text-align:right;color:${t.row_count===0?'var(--t3)':'inherit'}">${t.row_count}</td>
        </tr>`).join('')}</tbody>
      </table>`;
    }
  } catch(e) {
    if (statsEl) statsEl.innerHTML = `<div style="color:var(--red,#e55)">${_esc(e.message)}</div>`;
  }
}

async function sysDbBackup(btn) {
  btn.disabled = true; btn.textContent = '⏳';
  try {
    const token = localStorage.getItem(ADMIN_TOKEN_KEY) || '';
    const resp = await fetch('/api/admin/db/backup', { headers: { Authorization: `Bearer ${token}` } });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `ai_gm_backup_${Date.now()}.db`; a.click();
    URL.revokeObjectURL(url);
    showToast('Pobieranie rozpoczęte.', 'success');
  } catch(e) { showToast(e.message || 'Backup nieudany.', 'error'); }
  finally { btn.disabled = false; btn.textContent = '⬇ Pobierz backup'; }
}

async function sysDbMigrate(btn) {
  btn.disabled = true; btn.textContent = '⏳';
  try {
    await apiFetch('/api/admin/db/migrate', { method: 'POST' });
    showToast('Migracje zakończone.', 'success');
  } catch(e) { showToast(e.message || 'Migracje nieudane.', 'error'); }
  finally { btn.disabled = false; btn.textContent = '▶ Uruchom migracje'; }
}

async function sysDbRestore(btn) {
  const fileInp = document.getElementById('sys-restore-file');
  const f = fileInp?.files?.[0];
  if (!f) return;
  if (!confirm('Przywrócić bazę danych? Zastąpi bieżące dane — nie można cofnąć.')) return;
  btn.disabled = true; btn.textContent = '⏳';
  try {
    const fd = new FormData();
    fd.append('file', f);
    await apiFetch('/api/admin/db/restore', { method: 'POST', body: fd });
    showToast('Baza przywrócona.', 'success');
    if (fileInp) fileInp.value = '';
    btn.disabled = true;
  } catch(e) { showToast(e.message || 'Przywracanie nieudane.', 'error'); btn.disabled = false; }
  finally { if (btn.textContent === '⏳') btn.textContent = '🔁 Przywróć'; }
}

// ── Config tab ────────────────────────────────────────────────────────────────
function sysConfigFileChange() {
  const hasFile = !!document.getElementById('sys-config-file')?.files?.length;
  const dryBtn = document.getElementById('sys-dry-btn');
  const commitBtn = document.getElementById('sys-commit-btn');
  if (dryBtn) dryBtn.disabled = !hasFile;
  if (commitBtn) commitBtn.disabled = true;
  _sysConfigParsed = null;
  const diff = document.getElementById('sys-config-diff');
  if (diff) { diff.style.display = 'none'; diff.innerHTML = ''; }
}

async function sysConfigExport(btn) {
  btn.disabled = true; btn.textContent = '⏳';
  try {
    const data = await apiFetch('/api/admin/config/export');
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const d = new Date();
    a.download = `aigm_config_${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}.json`;
    a.click(); URL.revokeObjectURL(url);
    showToast('Konfiguracja wyeksportowana.', 'success');
  } catch(e) { showToast(e.message || 'Błąd eksportu.', 'error'); }
  finally { btn.disabled = false; btn.textContent = '⬇ Eksportuj'; }
}

async function sysConfigDryRun(btn) {
  const fileInp = document.getElementById('sys-config-file');
  const f = fileInp?.files?.[0];
  if (!f) return;
  btn.disabled = true; btn.textContent = '⏳';
  const commitBtn = document.getElementById('sys-commit-btn');
  const diffWrap = document.getElementById('sys-config-diff');
  _sysConfigParsed = null;
  try {
    const text = await f.text();
    const parsed = JSON.parse(text);
    if (!parsed?.tables) throw new Error('Nieprawidłowy plik: brak tables.');
    _sysConfigParsed = parsed;
    const res = await apiFetch('/api/admin/config/import?dry_run=true', { method: 'POST', body: JSON.stringify(parsed) });
    _sysConfigWarnings = res?.warnings || [];
    if (diffWrap) {
      diffWrap.style.display = '';
      const tables = parsed.tables || {};
      diffWrap.innerHTML = `
        <div style="font-size:0.8rem;font-weight:600;margin-bottom:6px">Dry Run — podgląd importu</div>
        ${_sysConfigWarnings.length ? `<div style="background:var(--amber,#f59e0b20);border:1px solid var(--amber,#f59e0b);border-radius:6px;padding:8px;font-size:0.78rem;margin-bottom:8px">${_sysConfigWarnings.map(w => _esc(w)).join('<br>')}</div>` : ''}
        <table class="data-table" style="font-size:0.78rem">
          <thead><tr><th>Tabela</th><th>Wiersze w pliku</th></tr></thead>
          <tbody>${Object.keys(tables).sort().map(k =>
            `<tr><td class="td-mono">${_esc(k)}</td><td>${Array.isArray(tables[k]) ? tables[k].length : 0}</td></tr>`
          ).join('')}</tbody>
        </table>`;
    }
    if (commitBtn) commitBtn.disabled = false;
    showToast(_sysConfigWarnings.length ? 'Dry run z ostrzeżeniami.' : 'Dry run OK.', 'success');
  } catch(e) {
    _sysConfigParsed = null;
    if (diffWrap) { diffWrap.style.display = 'none'; diffWrap.innerHTML = ''; }
    showToast(e instanceof SyntaxError ? 'Nieprawidłowy JSON.' : e.message || 'Błąd dry run.', 'error');
  } finally {
    btn.disabled = !fileInp?.files?.length;
    btn.textContent = '🔍 Dry Run';
  }
}

async function sysConfigCommit(btn) {
  if (!_sysConfigParsed) { showToast('Najpierw uruchom dry run.', 'info'); return; }
  if (!confirm('Zatwierdzić import? Bieżąca konfiguracja zostanie zastąpiona.' +
    (_sysConfigWarnings.length ? `\n\nOstrzeżenia:\n- ${_sysConfigWarnings.join('\n- ')}` : ''))) return;
  btn.disabled = true; btn.textContent = '⏳';
  try {
    await apiFetch('/api/admin/config/import', { method: 'POST', body: JSON.stringify(_sysConfigParsed) });
    showToast('Import zatwierdzony. Kopia DB utworzona automatycznie.', 'success');
    const fileInp = document.getElementById('sys-config-file');
    if (fileInp) fileInp.value = '';
    _sysConfigParsed = null;
    const diff = document.getElementById('sys-config-diff');
    if (diff) { diff.style.display = 'none'; }
    document.getElementById('sys-dry-btn').disabled = true;
    btn.disabled = true;
  } catch(e) {
    showToast(e.message || 'Błąd importu.', 'error');
    btn.disabled = false;
  } finally { if (btn.textContent === '⏳') btn.textContent = '✅ Zatwierdź import'; }
}

// ── Slash Commands tab ────────────────────────────────────────────────────────
async function _loadSysSlash() {
  _sysTabLoaded.add('slash');
  const rowsEl = document.getElementById('sys-slash-rows');
  const saveBtn = document.getElementById('sys-slash-save');
  if (!rowsEl) return;
  rowsEl.innerHTML = '<div style="padding:12px;color:var(--t3)">Ładowanie…</div>';
  try {
    const data = await apiFetch('/api/admin/slash-commands');
    const cmds = data.commands || [];
    rowsEl.innerHTML = cmds.map(c => {
      const adminOn = c.admin_enabled !== false;
      const playerOn = c.player_enabled !== undefined ? c.player_enabled !== false : c.enabled !== false;
      return `<div class="slash-cmd-row" data-cmd="${_esc(c.command||'')}" style="display:grid;grid-template-columns:140px 140px 56px 56px 1fr;gap:4px;align-items:start;padding:4px 0;border-bottom:1px solid var(--border)">
        <span class="td-mono" style="font-size:0.8rem;padding-top:6px">${_esc(c.command||'')}</span>
        <input type="text" class="slash-cmd-alias field-input" style="font-size:0.78rem;padding:4px 6px" value="${_esc(c.alias||'')}" maxlength="40" placeholder="alias" />
        <div style="text-align:center;padding-top:4px"><input type="checkbox" class="slash-cmd-admin" ${adminOn?'checked':''} /></div>
        <div style="text-align:center;padding-top:4px"><input type="checkbox" class="slash-cmd-player" ${playerOn?'checked':''} /></div>
        <textarea class="slash-cmd-desc field-input" rows="2" style="font-size:0.78rem;padding:4px 6px;resize:vertical">${_esc(c.description||'')}</textarea>
      </div>`;
    }).join('');
    if (saveBtn) saveBtn.disabled = false;
  } catch(e) {
    rowsEl.innerHTML = `<div style="padding:12px;color:var(--red,#e55)">${_esc(e.message)}</div>`;
  }
}

async function sysSlashSave(btn) {
  const rowsEl = document.getElementById('sys-slash-rows');
  if (!rowsEl) return;
  const rows = rowsEl.querySelectorAll('.slash-cmd-row');
  const commands = Array.from(rows).map(row => ({
    command: row.dataset.cmd,
    alias: row.querySelector('.slash-cmd-alias')?.value?.trim() || '',
    description: row.querySelector('.slash-cmd-desc')?.value?.trim() || '',
    admin_enabled: row.querySelector('.slash-cmd-admin')?.checked ?? true,
    player_enabled: row.querySelector('.slash-cmd-player')?.checked ?? false,
  }));
  btn.disabled = true; btn.textContent = '⏳';
  try {
    await apiFetch('/api/admin/slash-commands', { method: 'PUT', body: JSON.stringify({ commands }) });
    showToast('Komendy zapisane.', 'success');
  } catch(e) { showToast(e.message || 'Błąd zapisu.', 'error'); }
  finally { btn.disabled = false; btn.textContent = 'Zapisz komendy'; }
}

// ── Resurrection tab ──────────────────────────────────────────────────────────
async function _loadSysResurrection() {
  try {
    const cfg = await apiFetch('/api/admin/resurrection-config');
    const set = (id,v) => { const el = document.getElementById(id); if (el && v != null) el.value = v; };
    const enabledEl = document.getElementById('sys-res-enabled');
    if (enabledEl) enabledEl.checked = !!(cfg.enabled);
    set('sys-res-mode', cfg.mode || 'admin_free');
    set('sys-res-default', cfg.default_uses ?? '');
    set('sys-res-cap', cfg.cap_percent ?? '');
    set('sys-res-value', cfg.value ?? '');
    const btn = document.getElementById('sys-res-save');
    if (btn && !btn._wired) {
      btn._wired = true;
      btn.addEventListener('click', async () => {
        btn.disabled = true; const orig = btn.textContent; btn.textContent = '⏳';
        try {
          const payload = {
            enabled: !!(document.getElementById('sys-res-enabled')?.checked),
            mode: document.getElementById('sys-res-mode').value,
            default_uses: parseInt(document.getElementById('sys-res-default').value,10),
            cap_percent: parseInt(document.getElementById('sys-res-cap').value,10),
            value: document.getElementById('sys-res-value').value ? parseFloat(document.getElementById('sys-res-value').value) : null,
          };
          if (isNaN(payload.default_uses)) delete payload.default_uses;
          if (isNaN(payload.cap_percent)) delete payload.cap_percent;
          await apiFetch('/api/admin/resurrection-config', { method:'PATCH', body: JSON.stringify(payload) });
          showToast('Zapisano.', 'success');
        } catch(e) { showToast(e.message || 'Błąd.', 'error'); }
        finally { btn.disabled = false; btn.textContent = orig; }
      });
    }
  } catch(e) { showToast(e.message || 'Błąd ładowania konfiguracji.', 'error'); }
}

// ── Email tab ─────────────────────────────────────────────────────────────────
async function _loadSysEmail() {
  _sysTabLoaded.add('email');
  try {
    const d = await apiFetch('/api/admin/email/config');
    const g = id => document.getElementById(id);
    if (g('em-host')) g('em-host').value = d.smtp_host || '';
    if (g('em-port')) g('em-port').value = d.smtp_port || 587;
    if (g('em-tls'))  g('em-tls').checked = d.smtp_use_tls === '1' || d.smtp_use_tls === true || d.smtp_use_tls === 1;
    if (g('em-user')) g('em-user').value = d.smtp_username || '';
    if (g('em-from-addr')) g('em-from-addr').value = d.smtp_from_address || '';
    if (g('em-from-name')) g('em-from-name').value = d.smtp_from_name || '';
    if (g('em-reg-open'))  g('em-reg-open').checked = !!d.registration_open;
  } catch(e) { console.warn('email config', e.message); }
}

async function sysEmailSave(btn) {
  const g = id => document.getElementById(id);
  const body = {
    smtp_host: g('em-host')?.value?.trim() || '',
    smtp_port: String(parseInt(g('em-port')?.value) || 587),
    smtp_use_tls: g('em-tls')?.checked ? '1' : '0',
    smtp_username: g('em-user')?.value?.trim() || '',
    smtp_from_address: g('em-from-addr')?.value?.trim() || '',
    smtp_from_name: g('em-from-name')?.value?.trim() || '',
  };
  const pass = g('em-pass')?.value;
  if (pass) body.smtp_password = pass;
  btn.disabled = true; btn.textContent = '⏳';
  try {
    await apiFetch('/api/admin/email/config', { method: 'PATCH', body: JSON.stringify(body) });
    showToast('SMTP zapisany.', 'success');
    if (g('em-pass')) g('em-pass').value = '';
  } catch(e) { showToast(e.message || 'Błąd zapisu.', 'error'); }
  finally { btn.disabled = false; btn.textContent = 'Zapisz SMTP'; }
}

async function sysEmailTest(btn) {
  const to = document.getElementById('em-test-addr')?.value?.trim();
  if (!to) { showToast('Podaj adres testowy.', 'error'); return; }
  btn.disabled = true; btn.textContent = '⏳';
  try {
    await apiFetch('/api/admin/email/test', { method: 'POST', body: JSON.stringify({ to }) });
    showToast('Test wysłany — sprawdź skrzynkę.', 'success');
  } catch(e) { showToast(e.message || 'Błąd wysyłania.', 'error'); }
  finally { btn.disabled = false; btn.textContent = 'Wyślij test'; }
}

async function sysEmailSaveReg(btn) {
  const open = document.getElementById('em-reg-open')?.checked ?? false;
  btn.disabled = true; btn.textContent = '⏳';
  try {
    await apiFetch('/api/admin/email/config', { method: 'PATCH', body: JSON.stringify({ registration_open: open }) });
    showToast('Zapisano.', 'success');
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); }
  finally { btn.disabled = false; btn.textContent = 'Zapisz ustawienie'; }
}

// ── Visual tab ────────────────────────────────────────────────────────────────
async function _loadSysVisual() {
  _sysTabLoaded.add('visual');
  try {
    const [vis, bgs] = await Promise.all([
      apiFetch('/api/admin/visual'),
      apiFetch('/api/ui/backgrounds').catch(() => ({ backgrounds: {} })),
    ]);
    const s = vis.settings || {};

    const todEnabled = document.getElementById('vis-tod-enabled');
    if (todEnabled) todEnabled.checked = !!s['time_of_day.enabled'];
    const todMode = document.getElementById('vis-tod-mode');
    if (todMode) todMode.value = s['time_of_day.mode'] || 'bg';

    const periodsEl = document.getElementById('vis-periods');
    if (periodsEl) {
      periodsEl.innerHTML = _VIS_PERIODS.map(p => {
        const color = s[`time_of_day.${p.key}`]?.color || '#1a1a2e';
        const accent = s[`time_of_day.${p.key}`]?.accent || '#7c3aed';
        return `<div style="border:1px solid var(--border);border-radius:8px;padding:10px">
          <div style="font-weight:600;font-size:0.82rem;margin-bottom:8px">${p.label}</div>
          <div class="form-row" style="gap:6px">
            <label style="font-size:0.75rem">Kolor</label>
            <input type="color" value="${_esc(color)}" style="width:36px;height:28px;border:none;background:none;cursor:pointer"
              onchange="visSavePeriodColor('${p.key}','color',this.value)" />
          </div>
          <div class="form-row" style="gap:6px;margin-top:4px">
            <label style="font-size:0.75rem">Akcent</label>
            <input type="color" value="${_esc(accent)}" style="width:36px;height:28px;border:none;background:none;cursor:pointer"
              onchange="visSavePeriodColor('${p.key}','accent',this.value)" />
          </div>
          <div style="height:24px;border-radius:4px;margin-top:6px;background:linear-gradient(90deg,${color},${accent})"></div>
        </div>`;
      }).join('');
    }

    const bgGrid = document.getElementById('vis-bg-grid');
    if (bgGrid) {
      const bgMap = bgs.backgrounds || {};
      const _bgTs = Date.now();
      bgGrid.innerHTML = _VIS_SCREENS.map(scr => {
        const url = bgMap[scr];
        return `<div style="border:1px solid var(--border);border-radius:8px;padding:8px">
          <div style="font-size:0.75rem;font-weight:600;margin-bottom:6px">${scr}</div>
          ${url ? `<img src="${_esc(url)}?t=${_bgTs}" style="width:100%;height:60px;object-fit:cover;border-radius:4px;margin-bottom:6px" />` : `<div style="height:60px;background:var(--surface);border-radius:4px;margin-bottom:6px;display:flex;align-items:center;justify-content:center;color:var(--t3);font-size:0.7rem">Brak</div>`}
          <div style="display:flex;gap:4px;flex-wrap:wrap">
            <label class="btn btn-sm btn-secondary" style="padding:2px 6px;font-size:0.7rem;cursor:pointer">
              Wgraj<input type="file" accept="image/*" style="display:none" onchange="visUploadBg('${scr}',this)" />
            </label>
            <button class="btn btn-sm btn-secondary" style="padding:2px 6px;font-size:0.7rem" onclick="visPickBg('${scr}')">🖼 Galeria</button>
            ${url ? `<button class="btn btn-sm btn-danger" style="padding:2px 6px;font-size:0.7rem" onclick="visDeleteBg('${scr}',this)">Usuń</button>` : ''}
          </div>
        </div>`;
      }).join('');
    }
  } catch(e) { console.warn('visual', e.message); }
}

async function visSaveSetting(key, value) {
  try {
    await apiFetch(`/api/admin/visual/${encodeURIComponent(key)}`, { method: 'PATCH', body: JSON.stringify({ value }) });
  } catch(e) { showToast(e.message || 'Błąd zapisu.', 'error'); }
}

async function visSavePeriodColor(period, field, value) {
  const key = `time_of_day.${period}`;
  await visSaveSetting(`${key}.${field}`, value);
}

async function visUploadBg(screen, input) {
  const f = input.files?.[0];
  if (!f) return;
  const fd = new FormData(); fd.append('file', f);
  try {
    await apiFetch(`/api/admin/ui/bg/${screen}`, { method: 'POST', body: fd });
    showToast('Tło wgrane.', 'success');
    _sysTabLoaded.delete('visual'); await _loadSysVisual();
  } catch(e) { showToast(e.message || 'Błąd wgrywania.', 'error'); }
}

async function visDeleteBg(screen, btn) {
  if (!confirm(`Usunąć tło ekranu "${screen}"?`)) return;
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/ui/bg/${screen}`, { method: 'DELETE' });
    showToast('Usunięto.', 'success');
    _sysTabLoaded.delete('visual'); await _loadSysVisual();
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); btn.disabled = false; }
}

async function visPickBg(screen) {
  let modal = document.getElementById('vis-gallery-modal');
  if (modal) modal.remove();
  modal = document.createElement('div');
  modal.id = 'vis-gallery-modal';
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:9999;display:flex;align-items:center;justify-content:center';
  modal.innerHTML = `<div style="background:var(--surface);border-radius:12px;width:min(720px,95vw);max-height:85vh;display:flex;flex-direction:column;overflow:hidden">
    <div style="padding:14px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-shrink:0">
      <strong>Galeria obrazów — ekran: ${screen}</strong>
      <button onclick="document.getElementById('vis-gallery-modal').remove()" style="background:none;border:none;color:var(--t2);font-size:1.2rem;cursor:pointer;line-height:1">✕</button>
    </div>
    <div id="vis-gallery-grid" style="padding:12px;overflow-y:auto;flex:1;display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px">
      <div style="grid-column:1/-1;text-align:center;padding:20px;color:var(--t3)">Ładowanie...</div>
    </div>
  </div>`;
  document.body.appendChild(modal);
  modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });

  const grid = document.getElementById('vis-gallery-grid');
  try {
    const data = await apiFetch('/api/admin/images/list');
    const imgs = data.images || [];
    if (!imgs.length) {
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:20px;color:var(--t3)">Brak obrazów w galerii. Wygeneruj je w zakładce Lokacje.</div>';
      return;
    }
    grid.innerHTML = imgs.map(img => {
      const enc = encodeURIComponent(img.url);
      const encF = encodeURIComponent(img.filename);
      return `<div onclick="visPickBgSelect('${_esc(screen)}','${enc}','${encF}')"
           style="border:2px solid var(--border);border-radius:6px;overflow:hidden;cursor:pointer;transition:border-color .15s"
           onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'">
        <img src="${_esc(img.url)}" style="width:100%;height:90px;object-fit:cover;display:block" loading="lazy" />
        <div style="padding:3px 5px;font-size:0.62rem;color:var(--t3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${_esc(img.filename)}">${_esc(img.filename)}</div>
      </div>`;
    }).join('');
  } catch(e) {
    grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--danger)">${_esc(e.message)}</div>`;
  }
}

async function visPickBgSelect(screen, encUrl, encFilename) {
  document.getElementById('vis-gallery-modal')?.remove();
  const filename = decodeURIComponent(encFilename);
  try {
    await apiFetch(`/api/admin/ui/bg/${screen}/from-tile`, {
      method: 'POST',
      body: JSON.stringify({ filename }),
    });
    showToast(`Tło ekranu "${screen}" ustawione.`, 'success');
    _sysTabLoaded.delete('visual');
    await _loadSysVisual();
  } catch(e) { showToast(e.message || 'Błąd.', 'error'); }
}

// ── Teksty tab (UI text CMS) ──────────────────────────────────────────────────
async function _loadSysTeksty() {
  try {
    const data = await apiFetch('/api/admin/ui-texts');
    _txtData = data.texts || [];
  } catch(e) { showToast(e.message || 'Błąd ładowania tekstów.', 'error'); return; }
  _renderTxtList();
}

function _renderTxtList() {
  const filter = document.getElementById('txt-screen-filter')?.value || '';
  const list = document.getElementById('txt-list');
  if (!list) return;
  const items = filter ? _txtData.filter(t => t.screen === filter) : _txtData;
  const badge = document.getElementById('txt-count-badge');
  if (badge) badge.textContent = items.length;
  list.innerHTML = '';
  if (!items.length) {
    list.innerHTML = '<p style="color:var(--t3);padding:12px;text-align:center">Brak tekstów w tej kategorii.</p>';
    return;
  }
  items.forEach(t => list.appendChild(_buildTxtCard(t)));
}

function _buildTxtCard(t) {
  const card = document.createElement('div');
  card.className = 'card';
  card.style.cssText = 'padding:14px;border-radius:10px;background:var(--bg2)';
  const hasOverride = t.custom_text != null || t.font_family || t.font_size || t.font_weight || t.color || t.text_transform || t.letter_spacing || t.extra_css;
  card.innerHTML = `
    <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:10px">
      <div style="flex:1">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <span style="font-family:monospace;font-size:0.78rem;background:var(--bg3);padding:2px 6px;border-radius:4px;color:var(--t2)">${t.key}</span>
          <span class="badge badge-slate" style="font-size:0.72rem">${t.screen || '—'}</span>
          ${hasOverride ? '<span class="badge badge-green" style="font-size:0.72rem">Zmieniony</span>' : ''}
        </div>
        <div style="margin-top:4px;font-size:0.82rem;color:var(--t3)">${t.description || ''}</div>
      </div>
      ${hasOverride ? `<button class="btn btn-sm btn-secondary" onclick="_txtReset('${t.key}',this)" style="white-space:nowrap;font-size:0.78rem">↺ Reset</button>` : ''}
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">
      <div>
        <label style="font-size:0.75rem;color:var(--t3);display:block;margin-bottom:3px">Oryginalny tekst</label>
        <div style="font-size:0.82rem;color:var(--t2);padding:6px 8px;background:var(--bg3);border-radius:6px;word-break:break-word">${_esc(t.original_text || '—')}</div>
      </div>
      <div>
        <label style="font-size:0.75rem;color:var(--t3);display:block;margin-bottom:3px">Własny tekst <span style="color:var(--t4)">(puste = oryginał)</span></label>
        <input type="text" class="field-input" data-txt-key="${t.key}" data-txt-field="custom_text"
          value="${_esc(t.custom_text || '')}"
          placeholder="${_esc(t.original_text || '')}"
          style="width:100%;font-size:0.82rem">
      </div>
    </div>
    <details style="margin-top:4px">
      <summary style="font-size:0.78rem;color:var(--t3);cursor:pointer;user-select:none">Formatowanie ▸</summary>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:8px">
        <div>
          <label style="font-size:0.75rem;color:var(--t3);display:block;margin-bottom:3px">Czcionka</label>
          <select class="field-input" data-txt-key="${t.key}" data-txt-field="font_family" style="width:100%;font-size:0.82rem">
            <option value="">—</option>
            <option value="Inter, sans-serif" ${t.font_family==='Inter, sans-serif'?'selected':''}>Inter</option>
            <option value="'Cinzel', serif" ${t.font_family==="'Cinzel', serif"?'selected':''}>Cinzel</option>
            <option value="'Lora', serif" ${t.font_family==="'Lora', serif"?'selected':''}>Lora</option>
            <option value="'Playfair Display', serif" ${t.font_family==="'Playfair Display', serif"?'selected':''}>Playfair Display</option>
            <option value="'IM Fell English', serif" ${t.font_family==="'IM Fell English', serif"?'selected':''}>IM Fell English</option>
            <option value="'Uncial Antiqua', cursive" ${t.font_family==="'Uncial Antiqua', cursive"?'selected':''}>Uncial Antiqua</option>
            <option value="monospace" ${t.font_family==='monospace'?'selected':''}>Monospace</option>
          </select>
        </div>
        <div>
          <label style="font-size:0.75rem;color:var(--t3);display:block;margin-bottom:3px">Rozmiar</label>
          <input type="text" class="field-input" data-txt-key="${t.key}" data-txt-field="font_size"
            value="${_esc(t.font_size || '')}" placeholder="np. 1.5rem, 24px"
            style="width:100%;font-size:0.82rem">
        </div>
        <div>
          <label style="font-size:0.75rem;color:var(--t3);display:block;margin-bottom:3px">Grubość</label>
          <select class="field-input" data-txt-key="${t.key}" data-txt-field="font_weight" style="width:100%;font-size:0.82rem">
            <option value="">—</option>
            <option value="400" ${t.font_weight==='400'?'selected':''}>400 (normal)</option>
            <option value="500" ${t.font_weight==='500'?'selected':''}>500 (medium)</option>
            <option value="600" ${t.font_weight==='600'?'selected':''}>600 (semibold)</option>
            <option value="700" ${t.font_weight==='700'?'selected':''}>700 (bold)</option>
          </select>
        </div>
        <div>
          <label style="font-size:0.75rem;color:var(--t3);display:block;margin-bottom:3px">Kolor</label>
          <div style="display:flex;gap:6px;align-items:center">
            <input type="color" data-txt-key="${t.key}" data-txt-field="color"
              value="${t.color || '#ffffff'}"
              style="width:36px;height:28px;border:none;border-radius:4px;cursor:pointer;background:transparent">
            <input type="text" class="field-input" data-txt-key="${t.key}" data-txt-field="color_hex"
              value="${_esc(t.color || '')}" placeholder="#ffffff"
              style="flex:1;font-size:0.82rem">
          </div>
        </div>
        <div>
          <label style="font-size:0.75rem;color:var(--t3);display:block;margin-bottom:3px">Transformacja</label>
          <select class="field-input" data-txt-key="${t.key}" data-txt-field="text_transform" style="width:100%;font-size:0.82rem">
            <option value="">—</option>
            <option value="uppercase" ${t.text_transform==='uppercase'?'selected':''}>UPPERCASE</option>
            <option value="lowercase" ${t.text_transform==='lowercase'?'selected':''}>lowercase</option>
            <option value="capitalize" ${t.text_transform==='capitalize'?'selected':''}>Capitalize</option>
            <option value="none" ${t.text_transform==='none'?'selected':''}>Brak</option>
          </select>
        </div>
        <div>
          <label style="font-size:0.75rem;color:var(--t3);display:block;margin-bottom:3px">Odstęp liter</label>
          <input type="text" class="field-input" data-txt-key="${t.key}" data-txt-field="letter_spacing"
            value="${_esc(t.letter_spacing || '')}" placeholder="np. 0.05em, 2px"
            style="width:100%;font-size:0.82rem">
        </div>
      </div>
      <div style="margin-top:8px">
        <label style="font-size:0.75rem;color:var(--t3);display:block;margin-bottom:3px">Dodatkowe CSS <span style="color:var(--t4)">(zaawansowane)</span></label>
        <input type="text" class="field-input" data-txt-key="${t.key}" data-txt-field="extra_css"
          value="${_esc(t.extra_css || '')}" placeholder="np. text-shadow: 0 2px 8px #000"
          style="width:100%;font-size:0.82rem">
      </div>
    </details>
    <div style="display:flex;justify-content:flex-end;margin-top:10px">
      <button class="btn btn-sm btn-primary" onclick="_txtSave('${t.key}',this)">Zapisz</button>
    </div>`;
  const colorPicker = card.querySelector(`input[type=color][data-txt-key="${t.key}"]`);
  const colorHex    = card.querySelector(`input[data-txt-field="color_hex"][data-txt-key="${t.key}"]`);
  if (colorPicker && colorHex) {
    colorPicker.addEventListener('input', () => { colorHex.value = colorPicker.value; });
    colorHex.addEventListener('input', () => {
      if (/^#[0-9a-f]{6}$/i.test(colorHex.value)) colorPicker.value = colorHex.value;
    });
  }
  return card;
}

async function _txtSave(key, btn) {
  btn.disabled = true;
  btn.textContent = '...';
  const container = btn.closest('.card');
  const pick = (field) => {
    const el = container.querySelector(`[data-txt-key="${key}"][data-txt-field="${field}"]`);
    return el ? (el.value.trim() || null) : undefined;
  };
  const payload = {
    custom_text:    pick('custom_text'),
    font_family:    pick('font_family'),
    font_size:      pick('font_size'),
    font_weight:    pick('font_weight'),
    color:          pick('color_hex'),
    text_transform: pick('text_transform'),
    letter_spacing: pick('letter_spacing'),
    extra_css:      pick('extra_css'),
  };
  Object.keys(payload).forEach(k => { if (payload[k] === undefined) delete payload[k]; });
  try {
    await apiFetch(`/api/admin/ui-texts/${key}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
    showToast('Zapisano.', 'success');
    const idx = _txtData.findIndex(t => t.key === key);
    if (idx >= 0) Object.assign(_txtData[idx], payload);
    _renderTxtList();
  } catch(e) {
    showToast(e.message || 'Błąd zapisu.', 'error');
    btn.disabled = false; btn.textContent = 'Zapisz';
  }
}

async function _txtReset(key, btn) {
  if (!confirm(`Przywrócić oryginalny tekst dla "${key}"?`)) return;
  btn.disabled = true;
  try {
    await apiFetch(`/api/admin/ui-texts/${key}/reset`, { method: 'POST' });
    showToast('Przywrócono oryginał.', 'success');
    await _loadSysTeksty();
  } catch(e) {
    showToast(e.message || 'Błąd.', 'error');
    btn.disabled = false;
  }
}

// ── Voice tab (TTS / STT / hosts / test console) ──────────────────────────────
async function _loadVoice() {
  const badge = document.getElementById('voice-status-badge');
  _loadVoiceHosts();
  try {
    const [health, config, voicesResp] = await Promise.all([
      apiFetch('/voice/healthz').catch(() => null),
      apiFetch('/voice/config'),
      apiFetch('/voice/voices').catch(() => ({ voices: [] })),
    ]);
    _voiceConfig = config;

    if (badge) badge.innerHTML = health ? '<span class="badge badge-green">● Online</span>' : '<span class="badge badge-amber">⚠ Niedostępny</span>';

    const setBadge = (id, val) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.innerHTML = val ? '<span class="badge badge-green">Włączony</span>' : '<span class="badge badge-slate">Wyłączony</span>';
    };
    const setInp = (id, val) => { const el = document.getElementById(id); if (el && val != null) el.value = val; };
    const setChk = (id, val) => { const el = document.getElementById(id); if (el) el.checked = !!val; };

    setBadge('v-tts-enabled', config.tts_enabled);
    setBadge('v-stt-enabled', config.stt_enabled);

    const voiceSel = document.getElementById('v-voice-select');
    if (voiceSel) {
      const voices = voicesResp.voices || [];
      voiceSel.innerHTML = voices.map(v => `<option value="${_esc(v)}" ${v===config.tts_voice?'selected':''}>${_esc(v)}</option>`).join('');
    }
    const setSlider = (inputId, valId, val, digits) => {
      const el = document.getElementById(inputId);
      const vEl = document.getElementById(valId);
      if (el && val != null) { el.value = val; }
      if (vEl && val != null) { vEl.textContent = digits != null ? parseFloat(val).toFixed(digits) : val; }
    };
    setSlider('v-tts-speed-input', 'v-tts-speed-val', config.tts_speed, 2);
    setSlider('v-tts-noise-input', 'v-tts-noise-val', config.tts_noise_scale, 2);
    setSlider('v-tts-nfe-input', 'v-tts-nfe-val', config.tts_nfe_step, 0);
    setSlider('v-tts-cfg-input', 'v-tts-cfg-val', config.tts_cfg_strength, 1);
    setSlider('v-tts-crossfade-input', 'v-tts-crossfade-val', config.tts_cross_fade_duration, 2);
    setSlider('v-tts-sway-input', 'v-tts-sway-val', config.tts_sway_sampling_coef, 2);
    const seedVal = config.tts_seed ?? -1;
    const seedRandom = seedVal === -1;
    const seedChk = document.getElementById('v-tts-seed-random');
    const seedInp = document.getElementById('v-tts-seed-input');
    if (seedChk) seedChk.checked = seedRandom;
    if (seedInp) { seedInp.value = seedVal; seedInp.disabled = seedRandom; }

    const modelSel = document.getElementById('v-stt-model-select');
    if (modelSel && config.stt_model) modelSel.value = config.stt_model;
    _renderWhisperPresets(config.stt_model || 'base');
    setInp('v-stt-lang-input', config.stt_language);
    setInp('v-stt-beam-input', config.stt_beam_size);
    setChk('v-stt-vad-check', config.vad_filter);
    setInp('v-stt-silence-input', config.stt_silence_auto_stop_ms);

    const routeKey = r => `aigm_tts_${r}`;
    document.querySelectorAll('#v-route-toggles input[data-vroute]').forEach(el => {
      const r = el.dataset.vroute;
      try { el.checked = localStorage.getItem(routeKey(r)) !== '0'; } catch { el.checked = true; }
      if (!el._wired) {
        el._wired = true;
        el.addEventListener('change', () => {
          try { localStorage.setItem(routeKey(r), el.checked ? '1' : '0'); } catch {}
          showToast(`${r}: ${el.checked ? 'TTS włączony' : 'TTS wyłączony'}`, 'info');
        });
      }
    });
  } catch(e) {
    if (badge) badge.innerHTML = '<span class="badge badge-red">✕ Błąd</span>';
    showToast('Głos: ' + e.message, 'error');
  }
}

function _onSeedRandomToggle() {
  const chk = document.getElementById('v-tts-seed-random');
  const inp = document.getElementById('v-tts-seed-input');
  if (!chk || !inp) return;
  inp.disabled = chk.checked;
  if (chk.checked) {
    inp.value = -1;
  } else {
    if (parseInt(inp.value, 10) === -1) inp.value = 42;
  }
}

async function saveTTSConfig(btn) {
  const voice = document.getElementById('v-voice-select')?.value;
  const speed = parseFloat(document.getElementById('v-tts-speed-input')?.value);
  const noise = parseFloat(document.getElementById('v-tts-noise-input')?.value);
  const nfe = parseInt(document.getElementById('v-tts-nfe-input')?.value, 10);
  const cfg = parseFloat(document.getElementById('v-tts-cfg-input')?.value);
  const crossfade = parseFloat(document.getElementById('v-tts-crossfade-input')?.value);
  const sway = parseFloat(document.getElementById('v-tts-sway-input')?.value);
  const seedRandom = document.getElementById('v-tts-seed-random')?.checked;
  const seed = seedRandom ? -1 : parseInt(document.getElementById('v-tts-seed-input')?.value, 10);
  const payload = {};
  if (voice) payload.tts_voice = voice;
  if (!isNaN(speed)) payload.tts_speed = speed;
  if (!isNaN(noise)) payload.tts_noise_scale = noise;
  if (!isNaN(nfe)) payload.tts_nfe_step = nfe;
  if (!isNaN(cfg)) payload.tts_cfg_strength = cfg;
  if (!isNaN(crossfade)) payload.tts_cross_fade_duration = crossfade;
  if (!isNaN(sway)) payload.tts_sway_sampling_coef = sway;
  if (!isNaN(seed)) payload.tts_seed = seed;
  if (btn) btn.disabled = true;
  try {
    await apiFetch('/voice/config', { method:'POST', body:JSON.stringify(payload) });
    _sysTabLoaded.delete('voice'); _loadVoice();
    showToast('TTS zapisano.', 'success');
  } catch(e) { showToast('Błąd: '+e.message, 'error'); }
  finally { if (btn) btn.disabled = false; }
}

function _renderWhisperPresets(activeModel) {
  const grid = document.getElementById('whisper-preset-grid');
  if (!grid) return;
  grid.innerHTML = _WHISPER_PRESETS.map(p => {
    const on = p.model === activeModel;
    return `<div class="preset-card${on?' active':''}" onclick="selectWhisperPreset('${p.model}')" style="cursor:pointer;padding:7px 9px">
      <div class="preset-card-top">
        <div class="preset-dot${on?' active':''}"></div>
        <span class="preset-name" style="font-size:0.8rem">${p.model}</span>
      </div>
      <div style="font-size:0.68rem;color:var(--t3)">${p.size} · ${p.vram}</div>
      <div style="font-size:0.68rem;color:${on?'var(--blue)':'var(--t2)'};margin-top:2px">${p.desc}</div>
    </div>`;
  }).join('');
}

async function selectWhisperPreset(model) {
  try {
    await apiFetch('/voice/config', { method:'POST', body:JSON.stringify({ stt_model:model }) });
    const sel = document.getElementById('v-stt-model-select');
    if (sel) sel.value = model;
    _renderWhisperPresets(model);
    showToast(`Model STT: ${model}`, 'success');
  } catch(e) { showToast('Błąd: '+e.message, 'error'); }
}

async function saveSTTConfig(btn) {
  const model = document.getElementById('v-stt-model-select')?.value;
  const lang = document.getElementById('v-stt-lang-input')?.value.trim();
  const beam = parseInt(document.getElementById('v-stt-beam-input')?.value, 10);
  const vad = document.getElementById('v-stt-vad-check')?.checked;
  const silence = parseInt(document.getElementById('v-stt-silence-input')?.value, 10);
  const payload = {};
  if (model) payload.stt_model = model;
  if (lang) payload.stt_language = lang;
  if (!isNaN(beam)) payload.stt_beam_size = beam;
  if (vad !== undefined) payload.vad_filter = vad;
  if (!isNaN(silence)) payload.stt_silence_auto_stop_ms = silence;
  if (btn) btn.disabled = true;
  try {
    await apiFetch('/voice/config', { method:'POST', body:JSON.stringify(payload) });
    _sysTabLoaded.delete('voice'); _loadVoice();
    showToast('STT zapisano.', 'success');
  } catch(e) { showToast('Błąd: '+e.message, 'error'); }
  finally { if (btn) btn.disabled = false; }
}

async function toggleVoiceTTS() {
  const current = _voiceConfig?.tts_enabled ?? false;
  try {
    await apiFetch('/voice/config', { method:'POST', body:JSON.stringify({ tts_enabled: !current }) });
    _sysTabLoaded.delete('voice'); _loadVoice();
    showToast(`TTS ${!current?'włączony':'wyłączony'}.`, 'success');
  } catch(e) { showToast('Błąd: '+e.message, 'error'); }
}

async function toggleVoiceSTT() {
  const current = _voiceConfig?.stt_enabled ?? false;
  try {
    await apiFetch('/voice/config', { method:'POST', body:JSON.stringify({ stt_enabled: !current }) });
    _sysTabLoaded.delete('voice'); _loadVoice();
    showToast(`STT ${!current?'włączony':'wyłączony'}.`, 'success');
  } catch(e) { showToast('Błąd: '+e.message, 'error'); }
}

async function _loadVoiceHosts() {
  const list = document.getElementById('voice-hosts-list');
  if (!list) return;
  try {
    const d = await apiFetch('/api/admin/voice/hosts');
    const hosts = d.items || [];
    const active = hosts.find(h => h.is_active);
    const lbl = document.getElementById('voice-active-label');
    if (lbl) lbl.textContent = active ? `aktywny: ${active.label}` : 'brak aktywnego';
    if (!hosts.length) { list.innerHTML = '<div style="color:var(--t3);font-size:0.82rem">Brak hostów.</div>'; return; }
    list.innerHTML = hosts.map(h => {
      const he = h.health || {};
      const online = he.online;
      const statusBadge = online
        ? '<span class="badge badge-green">● online</span>'
        : `<span class="badge badge-red">○ offline</span>`;
      const kindBadge = h.kind === 'gpu' ? '<span class="badge badge-amber">GPU</span>' : '<span class="badge badge-slate">CPU</span>';
      const model = online ? `TTS ${he.tts_loaded?'✓':'✗'} · STT ${he.stt_loaded?'✓':'✗'} · model: ${_esc(he.stt_model||'—')}` : _esc(he.error||'niedostępny');
      return `<div style="display:flex;align-items:center;gap:10px;padding:10px;border:1px solid ${h.is_active?'var(--blue-border)':'var(--border)'};border-radius:var(--r);background:${h.is_active?'var(--blue-light)':'var(--canvas)'}">
        <div style="flex:1;min-width:0">
          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
            <strong style="font-size:0.85rem">${_esc(h.label)}</strong> ${kindBadge} ${statusBadge}
            ${h.is_active?'<span class="badge badge-blue">aktywny</span>':''}
          </div>
          <div class="mono" style="font-size:0.72rem;color:var(--t3);margin-top:2px">${_esc(h.base_url)}</div>
          <div style="font-size:0.72rem;color:var(--t3);margin-top:2px">${model}${online&&he.available_voices?` · głosy: ${he.available_voices.length}`:''}</div>
        </div>
        <div style="display:flex;gap:6px;flex-shrink:0">
          ${h.is_active?'':`<button class="btn btn-primary btn-sm" onclick="setActiveVoiceHost(${h.id},this)">Aktywuj</button>`}
          ${h.is_active?'':`<button class="btn-icon danger" title="Usuń" onclick="deleteVoiceHost(${h.id},this)">✕</button>`}
        </div>
      </div>`;
    }).join('');
  } catch(e) { list.innerHTML = `<div style="color:var(--red);font-size:0.82rem">${_esc(e.message)}</div>`; }
}

async function setActiveVoiceHost(id, btn) {
  if (btn) btn.disabled = true;
  try {
    const r = await apiFetch(`/api/admin/voice/hosts/${id}`, { method:'PATCH', body:JSON.stringify({ is_active:true }) });
    showToast(`Aktywny host: ${r.label}.`, 'success');
    _sysTabLoaded.delete('voice'); _loadVoice();
  } catch(e) { showToast('Błąd: '+e.message, 'error'); if (btn) btn.disabled = false; }
}

async function addVoiceHost(btn) {
  const url = document.getElementById('vh-url')?.value.trim();
  const label = document.getElementById('vh-label')?.value.trim() || url;
  const kind = document.getElementById('vh-kind')?.value || 'cpu';
  if (!url) { showToast('Podaj URL hosta.', 'error'); return; }
  if (btn) btn.disabled = true;
  try {
    await apiFetch('/api/admin/voice/hosts', { method:'POST', body:JSON.stringify({ label, base_url:url, kind }) });
    showToast('Host dodany.', 'success');
    document.getElementById('vh-url').value = ''; document.getElementById('vh-label').value = '';
    _loadVoiceHosts();
  } catch(e) { showToast('Błąd: '+e.message, 'error'); }
  finally { if (btn) btn.disabled = false; }
}

async function deleteVoiceHost(id, btn) {
  if (!confirm('Usunąć ten host głosu?')) return;
  if (btn) btn.disabled = true;
  try {
    await apiFetch(`/api/admin/voice/hosts/${id}`, { method:'DELETE' });
    showToast('Host usunięty.', 'success');
    _loadVoiceHosts();
  } catch(e) { showToast('Błąd: '+e.message, 'error'); if (btn) btn.disabled = false; }
}

async function testTTS(btn) {
  const text = document.getElementById('vtest-text')?.value.trim();
  const status = document.getElementById('vtest-tts-status');
  if (!text) { showToast('Wpisz tekst.', 'error'); return; }
  btn.disabled = true; if (status) status.textContent = 'Generuję…';
  try {
    const speed = _voiceConfig?.tts_speed ?? 1.0;
    const url = `/voice/tts?text=${encodeURIComponent(text)}&speed=${speed}`;
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const blob = await r.blob();
    const audio = new Audio(URL.createObjectURL(blob));
    if (status) status.textContent = `OK — ${(blob.size/1024).toFixed(0)} KB, odtwarzam…`;
    audio.onended = () => { if (status) status.textContent = 'Gotowe.'; };
    await audio.play();
  } catch(e) { if (status) status.textContent = 'Błąd: '+e.message; showToast('TTS: '+e.message, 'error'); }
  finally { btn.disabled = false; }
}

async function testSTT(btn) {
  const out = document.getElementById('vtest-stt-out');
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio:true });
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/voice/stt`);
    _vtestWs = ws;
    ws.onmessage = (ev) => {
      try { const p = JSON.parse(ev.data||'{}'); if (p.text) out.textContent = `„${p.text}"`; else if (p.error) out.textContent = 'Błąd: '+p.error; }
      catch { /* ignore */ }
    };
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('WS error')); setTimeout(()=>rej(new Error('WS timeout')), 8000); });
    const mimes = ['audio/webm;codecs=opus','audio/webm','audio/mp4'];
    const mime = mimes.find(m => MediaRecorder.isTypeSupported(m));
    const rec = mime ? new MediaRecorder(stream,{mimeType:mime}) : new MediaRecorder(stream);
    _vtestRec = rec;
    rec.ondataavailable = (e) => { if (e.data?.size && ws.readyState===WebSocket.OPEN) ws.send(e.data); };
    rec.start(350);
    btn.disabled = true; out.textContent = 'Nagrywanie… (4 s)';
    setTimeout(() => {
      try { rec.stop(); } catch {}
      stream.getTracks().forEach(t => t.stop());
      if (ws.readyState===WebSocket.OPEN) { ws.send('__end__'); out.textContent = 'Transkrypcja…'; }
      setTimeout(() => { try { ws.close(); } catch {} btn.disabled = false; }, 4000);
    }, 4000);
  } catch(e) { out.textContent = 'Błąd: '+e.message; showToast('STT: '+e.message, 'error'); btn.disabled = false; }
}

// ── Image Gen tab ─────────────────────────────────────────────────────────────
async function _refreshImageGenModels(savedCheckpoint) {
  const sel = document.getElementById('ig-checkpoint');
  if (!sel) return;
  try {
    const r = await apiFetch('/api/admin/images/models');
    _igModels = r.models || [];
    const current = savedCheckpoint !== undefined ? savedCheckpoint : sel.value;
    sel.innerHTML = '<option value="">(domyślny serwisu)</option>' +
      _igModels.map(m => `<option value="${_esc(m.key)}" title="${_esc(m.hint||'')}">${_esc(m.label)}</option>`).join('');
    if (current) sel.value = current;
    _updateIgModelHint(false);
  } catch(e) { console.warn('models load failed:', e.message); }
}

function _updateIgModelHint(autoFillSteps = true) {
  const sel = document.getElementById('ig-checkpoint');
  const hintEl = document.getElementById('ig-model-hint');
  if (!sel || !hintEl) return;
  const m = _igModels.find(x => x.key === sel.value);
  if (m) {
    hintEl.textContent = m.hint || '';
    if (autoFillSteps) {
      const stepsEl = document.getElementById('ig-steps');
      const refEl = document.getElementById('ig-refine-steps');
      if (stepsEl && m.default_steps_t2i) stepsEl.value = m.default_steps_t2i;
      if (refEl && m.default_steps_i2i) refEl.value = m.default_steps_i2i;
    }
  } else {
    hintEl.textContent = '';
  }
}

async function _loadSysImageGen() {
  try {
    const cfg = await apiFetch('/api/admin/images/config');
    const set = (id, v) => { const el = document.getElementById(id); if (el && v != null) el.value = v; };
    set('ig-url', cfg.url || '');
    set('ig-steps', cfg.steps ?? 4);
    set('ig-refine-steps', cfg.refine_steps ?? 8);
    const pSel = document.getElementById('ig-portrait-size');
    if (pSel) pSel.value = `${cfg.portrait_width ?? 576}x${cfg.portrait_height ?? 1024}`;

    await _refreshImageGenModels(cfg.checkpoint || '');

    const sel = document.getElementById('ig-checkpoint');
    if (sel && !sel._wired) {
      sel._wired = true;
      sel.addEventListener('change', _updateIgModelHint);
    }

    try {
      const gd = await apiFetch('/api/admin/images/list');
      const imgs = gd.images || [];
      const totalKb = imgs.reduce((s, i) => s + (i.size || 0), 0) / 1024;
      const statsEl = document.getElementById('imagegen-gallery-stats');
      if (statsEl) statsEl.innerHTML = `Obrazów: <strong>${imgs.length}</strong> &nbsp;·&nbsp; Rozmiar: <strong>${totalKb.toFixed(0)} KB</strong>`;
    } catch {}

    const saveBtn = document.getElementById('ig-save-btn');
    if (saveBtn && !saveBtn._wired) {
      saveBtn._wired = true;
      saveBtn.addEventListener('click', async () => {
        saveBtn.disabled = true;
        const orig = saveBtn.textContent; saveBtn.textContent = '⏳';
        try {
          const pSize = (document.getElementById('ig-portrait-size')?.value || '576x1024').split('x');
          const payload = {
            url: document.getElementById('ig-url').value.trim() || null,
            checkpoint: document.getElementById('ig-checkpoint').value.trim(),
            steps: parseInt(document.getElementById('ig-steps').value, 10) || null,
            refine_steps: parseInt(document.getElementById('ig-refine-steps').value, 10) || null,
            portrait_width: parseInt(pSize[0], 10) || 576,
            portrait_height: parseInt(pSize[1], 10) || 1024,
          };
          if (isNaN(payload.steps)) payload.steps = null;
          if (isNaN(payload.refine_steps)) payload.refine_steps = null;
          await apiFetch('/api/admin/images/config', { method: 'PATCH', body: JSON.stringify(payload) });
          showToast('Zapisano ustawienia generatora.', 'success');
          _sysTabLoaded.delete('imagegen');
          _loadSysImageGen();
        } catch(e) { showToast(e.message || 'Błąd zapisu.', 'error'); }
        finally { saveBtn.disabled = false; saveBtn.textContent = orig; }
      });
    }
  } catch(e) { showToast(e.message || 'Błąd ładowania konfiguracji obrazów.', 'error'); }
}

async function _pingImageGen() {
  const statusEl = document.getElementById('imagegen-status');
  if (statusEl) { statusEl.textContent = '⏳ Sprawdzam…'; statusEl.style.color = 'var(--t3)'; }
  try {
    const r = await apiFetch('/api/admin/images/status');
    if (statusEl) {
      if (r.online) {
        const extra = r.data && Object.keys(r.data).length ? ' — ' + JSON.stringify(r.data) : '';
        statusEl.innerHTML = `<span style="color:var(--success)">✓ Online</span> <span style="color:var(--t3);font-size:0.78rem">${_esc(r.url)}${_esc(extra)}</span>`;
      } else {
        statusEl.innerHTML = `<span style="color:var(--danger)">✕ Offline</span> <span style="color:var(--t3);font-size:0.78rem">${_esc(r.url)} — ${_esc(r.error||'')}</span>`;
      }
    }
  } catch(e) {
    if (statusEl) { statusEl.textContent = 'Błąd: ' + (e.message || 'nieznany'); statusEl.style.color = 'var(--danger)'; }
  }
}

// ── Narration tab ─────────────────────────────────────────────────────────────
async function _loadNarration() {
  try {
    const d = await apiFetch('/api/admin/prompts/system_prompt');
    const ta = document.getElementById('prompt-textarea');
    if (ta && d?.content) ta.value = d.content;
  } catch(e) { console.warn('narration', e.message); }
  // E9 (#424) — Story Gravity config load + save wiring.
  try {
    const r = await apiFetch('/api/settings/story-gravity');
    const c = r.data || {};
    const set = (id, v) => { const el = document.getElementById(id); if (el) { if (el.type === 'checkbox') el.checked = !!v; else el.value = v; } };
    set('sys-sg-enabled', c.enabled); set('sys-sg-l1', c.turns_l1); set('sys-sg-l2', c.turns_l2); set('sys-sg-l3', c.turns_l3); set('sys-sg-l3-enabled', c.l3_enabled); set('sys-sg-l3-enabled-gotowa', c.l3_enabled_gotowa ?? true);
  } catch(e) { console.warn('story-gravity', e.message); }
  const sgBtn = document.getElementById('sys-sg-save');
  if (sgBtn && !sgBtn.dataset.wired) {
    sgBtn.dataset.wired = '1';
    sgBtn.addEventListener('click', async () => {
      const num = id => parseInt(document.getElementById(id)?.value, 10);
      const payload = {
        enabled: document.getElementById('sys-sg-enabled')?.checked ?? true,
        turns_l1: num('sys-sg-l1'), turns_l2: num('sys-sg-l2'), turns_l3: num('sys-sg-l3'),
        l3_enabled: document.getElementById('sys-sg-l3-enabled')?.checked ?? false,
        l3_enabled_gotowa: document.getElementById('sys-sg-l3-enabled-gotowa')?.checked ?? true,
      };
      try {
        await apiFetch('/api/settings/story-gravity', { method: 'PATCH', body: JSON.stringify(payload) });
        showToast('Progi Story Gravity zapisane.', 'success');
      } catch(e) { showToast(e.message || 'Błąd zapisu.', 'error'); }
    });
  }
  // Combat narrative global toggle
  try {
    const cnr = await apiFetch('/api/admin/config/combat-narrative');
    const el = document.getElementById('sys-skip-combat-narr');
    if (el) el.checked = !!cnr?.skip_combat_narrative;
  } catch(e) { console.warn('combat-narrative-cfg', e.message); }
  const cnBtn = document.getElementById('sys-skip-combat-narr-save');
  if (cnBtn && !cnBtn.dataset.wired) {
    cnBtn.dataset.wired = '1';
    cnBtn.addEventListener('click', async () => {
      const skip = document.getElementById('sys-skip-combat-narr')?.checked ?? false;
      try {
        await apiFetch('/api/admin/config/combat-narrative', { method: 'PATCH', body: JSON.stringify({ skip_combat_narrative: skip }) });
        showToast(skip ? 'Narracja bojowa wyłączona globalnie.' : 'Narracja bojowa włączona.', 'success');
      } catch(e) { showToast(e.message || 'Błąd zapisu.', 'error'); }
    });
  }
}

function togglePromptEdit() {
  const ta = document.getElementById('prompt-textarea');
  const btn = document.getElementById('prompt-edit-btn');
  const editing = ta.disabled;
  ta.disabled = !editing;
  btn.textContent = editing ? '✓ Zapisz' : '✎ Edytuj';
  if (editing) ta.focus();
}

function setTone(btn) {
  document.querySelectorAll('.tone-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const tones = {
    'Formalny': 'Formalny: narracja utrzymana w poważnym, kronikarskim stylu. Idealna dla mrocznych, politycznych kampanii.',
    'Zrównoważony': 'Zrównoważony: narracja zachowuje powagę sytuacji bez przesadnego dramatyzmu. Dobry dla większości sesji.',
    'Dramatyczny': 'Dramatyczny: intensywna, emocjonalna narracja z bogatymi opisami. Podkreśla napięcie i stawkę każdej sceny.',
  };
  const desc = document.getElementById('tone-desc');
  if (desc) desc.textContent = tones[btn.textContent.trim()] || '';
}

// ── Game modes tab ────────────────────────────────────────────────────────────
async function _loadGameModes() {
  try {
    const d = await apiFetch('/api/admin/game-modes');
    const flags = d.flags || {};
    const set = (id, key) => { const el = document.getElementById(id); if (el) el.checked = flags[key] !== false; };
    set('gm-ai-campaign',    'ai_campaign_enabled');
    set('gm-prebuilt',       'prebuilt_enabled');
    set('gm-dungeon',        'dungeon_enabled');
    set('gm-multiplayer',    'multiplayer_enabled');
  } catch(e) { console.warn('game-modes load', e.message); }
}

async function saveGameModes() {
  const get = id => document.getElementById(id)?.checked ?? true;
  try {
    await apiFetch('/api/admin/game-modes', {
      method: 'PATCH',
      body: JSON.stringify({
        ai_campaign_enabled:   get('gm-ai-campaign'),
        prebuilt_enabled:      get('gm-prebuilt'),
        dungeon_enabled:       get('gm-dungeon'),
        multiplayer_enabled:   get('gm-multiplayer'),
      }),
    });
    showToast('Tryby gry zapisane', 'success');
  } catch(e) { showToast('Błąd zapisu: ' + e.message, 'error'); }
}

// ── Entry point ───────────────────────────────────────────────────────────────
export async function init(panel) {
  _sysTabLoaded.clear();
  panel.innerHTML = _HTML;
  _wireSysTabs();
  _loadSysTab('llm');

  // Funkcje wołane z onclick= w HTML muszą żyć na window (port 1:1 z monolitu).
  Object.assign(window, {
    sysUseEnv, openPresetModal, activatePreset, deletePreset, savePreset,
    _reloadSysDb, sysDbBackup, sysDbMigrate, sysDbRestore,
    sysConfigFileChange, sysConfigDryRun, sysConfigCommit, sysConfigExport,
    sysSlashSave,
    sysEmailSave, sysEmailTest, sysEmailSaveReg,
    visSaveSetting, visSavePeriodColor, visUploadBg, visDeleteBg, visPickBg, visPickBgSelect,
    _loadSysTeksty, _txtSave, _txtReset,
    saveTTSConfig, saveSTTConfig, toggleVoiceTTS, toggleVoiceSTT,
    setActiveVoiceHost, addVoiceHost, deleteVoiceHost,
    testTTS, testSTT, _onSeedRandomToggle, selectWhisperPreset,
    _pingImageGen, _refreshImageGenModels,
    togglePromptEdit, setTone, saveGameModes,
  });
}
