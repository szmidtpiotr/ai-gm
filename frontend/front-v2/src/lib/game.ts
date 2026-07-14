// F-12 ekran gry — pochodne stanu postaci + normalizacja strumienia tur.
// Źródło prawdy tokenów/konwencji: frontend_design.md sekcja 6.
import type {
  HeroSheet,
  RollCardData,
  SkillTestPending,
  SuggestedAction,
  TurnHistoryEntry,
  TurnResponse,
} from "@/lib/types";

// ── Arkusz → paski żywotności ────────────────────────────────────────────────
// Klucze bywają niespójne w danych (hp_current/hp, gold_gp/gold) — czytamy defensywnie.

export interface Vitals {
  hp: number;
  maxHp: number;
  mana: number;
  maxMana: number;
  hasMana: boolean;
  level: number;
  gold: number;
  xp: number;
  maxXp: number;
}

function num(v: unknown, fallback = 0): number {
  const n = typeof v === "string" ? Number(v) : (v as number);
  return Number.isFinite(n) ? (n as number) : fallback;
}

export function readVitals(sheet: HeroSheet | undefined): Vitals {
  const s = sheet ?? {};
  const maxHp = num(s.max_hp ?? s.hp, 1) || 1;
  const hp = num(s.hp_current ?? s.hp, maxHp);
  const maxMana = num(s.max_mana, 0);
  const mana = num(s.current_mana, maxMana);
  const xpNext = num((s as Record<string, unknown>).xp_to_next, 0);
  return {
    hp: Math.max(0, hp),
    maxHp,
    mana: Math.max(0, mana),
    maxMana,
    hasMana: maxMana > 0,
    level: num(s.level, 1) || 1,
    gold: num(s.gold_gp ?? s.gold, 0),
    xp: num((s as Record<string, unknown>).xp, 0),
    maxXp: xpNext || 0,
  };
}

const STAT_KEYS = ["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"] as const;

export function readStats(sheet: HeroSheet | undefined): Array<{ k: string; v: number }> {
  const raw = ((sheet ?? {}) as Record<string, unknown>).stats;
  const stats = (raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {}) ?? {};
  return STAT_KEYS.map((k) => ({
    k,
    v: num(stats[k] ?? stats[k.toLowerCase()], 0),
  }));
}

// ── Strumień tur → bloki logu ────────────────────────────────────────────────
// Każda tura = opcjonalna akcja gracza (user_text) + narracja GM (assistant_text).
// Systemowe wtręty (JSON-owe tagi w tekście) obcinamy — narrator zwykle je już czyści.

export type LogBlock =
  | { kind: "player"; id: string; text: string }
  | { kind: "gm"; id: string; text: string; turn: number }
  | { kind: "system"; id: string; text: string }
  | { kind: "roll"; id: string; roll: RollCardData }
  // #1379: `tone`/`icon` opcjonalne — completion band koloruje wg tonu zdarzenia
  // systemowego (success/info/warning/danger); brak = domyślny zielony (beat/quest).
  | { kind: "completion"; id: string; text: string; tone?: SystemEventTone; icon?: string }
  | { kind: "gold"; id: string; delta: number; label: string };

// #1379 — ton komunikatu systemowego steruje kolorem środkowego dymka.
export type SystemEventTone = "success" | "info" | "warning" | "danger";

// Sztuczne komendy / puste akcje otwierające — nie pokazujemy jako dymka gracza.
function isVisiblePlayerText(t: string | null | undefined): boolean {
  if (!t) return false;
  const s = t.trim();
  if (!s) return false;
  if (s.startsWith("__AI_GM") || s.startsWith("[") ) return false;
  return true;
}

// Klucze cue'ów doklejane przez narratora obok prozy (JSON) — sygnał końca narracji.
const CUE_KEY_RE =
  /,?\s*"(location_intent|suggested_actions|grant_item|grant_gold|grant_gold_amount|open_shop|combat|combat_start|scene_advance|beat_complete|apply_condition|npc_dialogue)"\s*:/;

// Wyciąga prozę z assistant_text: obsługuje 3 kształty danych w bazie —
//  (1) czysta proza, (2) pełny obiekt JSON `{"narration": "...", ...cue'y}`,
//  (3) proza + doklejony ogon JSON w tej samej linii. LLM bywa niespójny.
// Wewnętrzne znaczniki silnika (np. __AI_GM_GM_ROLL_V1__) — nie pokazujemy.
function isSentinelProse(s: string): boolean {
  const t = s.trim();
  return /^__AI_GM/i.test(t) || /^_{2}[A-Z0-9_]+_{2}$/.test(t);
}

// #1299: narrator czasem dokleja "Roll <skill> d20" jako OSTATNIĄ linię narracji
// zamiast pola roll_cue. Backend to przechwytuje (odpala popup) i tnie, ale defensywnie
// usuwamy też tu — inaczej wyciek pokazuje się w logu (stare tury sprzed fixu +
// tor strumieniowy, który już wysłał tokeny na żywo). Gracz nie ma widzieć tej dyrektywy.
function stripTrailingRollCue(s: string): string {
  return s.replace(/\s*(?:\n|^)Roll\s+[^\n]+?\s+d\d+\s*$/i, "").trimEnd();
}

function cleanProse(text: string): string {
  let s = (text || "").trim();
  if (!s || isSentinelProse(s)) return "";

  // (2) pełny obiekt JSON → pole narracyjne
  if (s.startsWith("{")) {
    try {
      const o = JSON.parse(s) as Record<string, unknown>;
      const f =
        o.narration ?? o.narrative ?? o.prose ?? o.text ?? o.message ?? o.story;
      if (typeof f === "string" && f.trim()) return stripTrailingRollCue(f.trim());
    } catch {
      /* nie-poprawny JSON → tnij regexem poniżej */
    }
  }

  // (3) proza + ogon cue-JSON w tej samej linii
  const m = s.match(CUE_KEY_RE);
  if (m && m.index !== undefined) {
    let head = s.slice(0, m.index);
    head = head.replace(/["',\s]+$/, "").trim(); // domknięcie stringa narracji
    head = head.replace(
      /^\{\s*"(narration|narrative|prose|text|message|story)"\s*:\s*"/,
      "",
    ); // wiodące `{"narration": "`
    if (head) return stripTrailingRollCue(head.trim());
  }

  // (3b) samodzielny blok JSON w nowej linii na końcu
  const brace = s.lastIndexOf("\n{");
  if (brace > 0 && s.trimEnd().endsWith("}")) s = s.slice(0, brace).trim();
  return stripTrailingRollCue(s);
}

// Chipy z ostatniej tury GM (gdy odpowiedź live jeszcze ich nie dała) — parsuje
// suggested_actions z assistant_text (pełny JSON lub doklejony ogon).
export function chipsFromTurns(turns: TurnHistoryEntry[]): Chip[] {
  for (let i = turns.length - 1; i >= 0; i--) {
    const raw = (turns[i].assistant_text || "").trim();
    if (!raw.includes("suggested_actions")) continue;
    // spróbuj pełny JSON
    let actions: unknown = null;
    if (raw.startsWith("{")) {
      try {
        actions = (JSON.parse(raw) as Record<string, unknown>).suggested_actions;
      } catch {
        /* fallthrough */
      }
    }
    // fallback: wytnij fragment tablicy `"suggested_actions": [ ... ]`
    if (!Array.isArray(actions)) {
      const mm = raw.match(/"suggested_actions"\s*:\s*(\[[\s\S]*?\])\s*[},]/);
      if (mm) {
        try {
          actions = JSON.parse(mm[1]);
        } catch {
          /* ignore */
        }
      }
    }
    if (Array.isArray(actions)) return normalizeChips(actions as SuggestedAction[]);
    return [];
  }
  return [];
}

// Wydziela top-level obiekty JSON z tekstu (skaner zbalansowanych nawiasów,
// świadomy stringów) + fragmenty czystej prozy pomiędzy nimi, w kolejności.
type Segment = { json: Record<string, unknown> } | { text: string };

function extractSegments(raw: string): Segment[] {
  const segs: Segment[] = [];
  const s = raw || "";
  let i = 0;
  let textStart = 0;
  while (i < s.length) {
    if (s[i] === "{") {
      const end = matchBrace(s, i);
      if (end > i) {
        const before = s.slice(textStart, i).trim();
        if (before) segs.push({ text: before });
        try {
          segs.push({ json: JSON.parse(s.slice(i, end + 1)) });
        } catch {
          segs.push({ text: s.slice(i, end + 1) });
        }
        i = end + 1;
        textStart = i;
        continue;
      }
    }
    i++;
  }
  const tail = s.slice(textStart).trim();
  if (tail) segs.push({ text: tail });
  return segs;
}

// Zwraca indeks `}` domykającego `{` na pozycji start; -1 gdy niezbalansowane.
function matchBrace(s: string, start: number): number {
  let depth = 0;
  let inStr = false;
  for (let i = start; i < s.length; i++) {
    const c = s[i];
    if (inStr) {
      if (c === "\\") i++;
      else if (c === '"') inStr = false;
    } else if (c === '"') inStr = true;
    else if (c === "{") depth++;
    else if (c === "}") {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

const PROSE_FIELDS = ["narration", "narrative", "prose", "text", "message", "story"];
const ROLL_HINTS = ["skill", "dice", "verdict", "player_roll", "d20", "outcome"];

function objProse(o: Record<string, unknown>): string | null {
  for (const f of PROSE_FIELDS) {
    const v = o[f];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return null;
}

function isRollObj(o: Record<string, unknown>): boolean {
  return ROLL_HINTS.some((k) => k in o) && ("total" in o || "dice" in o || "d20" in o || "player_roll" in o);
}

const VERDICT_PL: Record<string, string> = {
  dodged: "UNIK",
  hit: "TRAFIENIE",
  miss: "PUDŁO",
  missed: "PUDŁO",
  success: "SUKCES",
  succeeded: "SUKCES",
  fail: "PORAŻKA",
  failed: "PORAŻKA",
  crit: "KRYTYK",
  fumble: "PECH",
};

function rollFromObj(o: Record<string, unknown>): RollCardData {
  const d20 = num(o.player_roll ?? o.d20 ?? o.raw, NaN);
  const mod = num(o.modifier, NaN);
  const total = num(o.total, NaN);
  const dc = num(o.dc, NaN);
  const verdict = String(o.verdict ?? o.outcome ?? "").toLowerCase();
  const title = String(o.skill ?? o.action ?? o.action_type ?? "RZUT").toUpperCase();
  const enemy =
    "enemy" in o || "attacker" in o || "monster" in o || /wróg|bandyt.*atak|atak.*wróg/.test(title.toLowerCase());
  const crit = d20 === 20 || verdict.includes("crit") || verdict.includes("kryt");
  const fumble = d20 === 1 || verdict.includes("fumble") || verdict.includes("pech");

  const cells: RollCardData["cells"] = [];
  if (Number.isFinite(d20)) cells.push({ k: "d20", v: String(d20) });
  if (Number.isFinite(mod)) cells.push({ k: "Mod", v: (mod >= 0 ? "+" : "") + mod });
  if (Number.isFinite(total)) cells.push({ k: "Suma", v: String(total), sum: true });
  if (Number.isFinite(dc)) cells.push({ k: "DC", v: String(dc) });
  cells.push({
    k: "Wynik",
    v: VERDICT_PL[verdict] ?? (verdict ? verdict.toUpperCase() : crit ? "KRYTYK" : fumble ? "PECH" : "—"),
    res: true,
  });

  return { actor: enemy ? "enemy" : "player", title: `TEST: ${title}`, cells, crit, fumble };
}

// #1299: wiersz rzutu z backendu "[Rzut: <skill> — <d20> <±mod> = <suma>[ vs …] — <wynik>]"
// jest persystowany jako user_text, ale ukryty przez isVisiblePlayerText (`[`-prefix).
// Zamień go na kartę rzutu, żeby po animacji kości nazwa+liczby zostały widoczne w logu
// (parytet z walką) — inaczej widać samą narrację GM i gracz myśli, że coś się zawiesiło.
const RZUT_RE =
  /^\[Rzut:\s*(.+?)\s+[—–-]\s+(\d+)\s+([+\-−]\d+)\s+=\s+(\d+)(.*?)\s+[—–-]\s+([^\]]+)\]\s*$/;

export function rollFromRzutLine(text: string | null | undefined): RollCardData | null {
  if (!text) return null;
  const m = text.trim().match(RZUT_RE);
  if (!m) return null;
  const label = m[1].trim();
  const d20 = parseInt(m[2], 10);
  const mod = m[3].replace("−", "-");
  const total = m[4];
  const outcome = m[6].trim();
  const lo = outcome.toLowerCase();
  // #1299: złoty KRYTYK / krwawy PECH tylko dla PRAWDZIWEGO nat20/nat1 (d20=20/1).
  // Skala testu (#581) ma osobny „Krytyczny sukces/porażka" wg marginesu (≥5) — to
  // MOCNY wynik, ale NIE nat20; pokazujemy go jako SUKCES+/PORAŻKA− bez złotej poświaty,
  // inaczej gracz widzi „KRYTYK" przy d20=14 i myśli, że to błąd.
  const nat20 = d20 === 20 || lo.startsWith("naturalny 20");
  const nat1 = d20 === 1 || lo.startsWith("naturalny 1");
  const marginCritSucc = !nat20 && lo.includes("krytyczny sukces");
  const marginCritFail = !nat1 && lo.includes("krytyczna porażka");
  const success = nat20 || marginCritSucc || lo.startsWith("sukces");

  const verdict = nat20
    ? "KRYTYK"
    : nat1
      ? "PECH"
      : marginCritSucc
        ? "SUKCES+"
        : marginCritFail
          ? "PORAŻKA−"
          : success
            ? "SUKCES"
            : "PORAŻKA";

  const cells: RollCardData["cells"] = [
    { k: "d20", v: String(d20) },
    { k: "Mod", v: mod },
    { k: "Suma", v: total, sum: true },
    { k: "Wynik", v: verdict, res: true, tone: success ? "ok" : "bad" },
  ];
  // crit/fumble = tylko złota/krwawa poświata karty → zarezerwowane dla nat20/nat1.
  return { actor: "player", title: `TEST: ${label.toUpperCase()}`, cells, crit: nat20, fumble: nat1 };
}

export function buildLog(turns: TurnHistoryEntry[]): LogBlock[] {
  const blocks: LogBlock[] = [];
  for (const t of turns) {
    if (isVisiblePlayerText(t.user_text)) {
      blocks.push({
        kind: "player",
        id: `p-${t.turn_number}`,
        text: t.user_text!.trim(),
      });
    } else {
      // #1299: ukryty player-text może być wierszem rzutu → karta w logu.
      const rc = rollFromRzutLine(t.user_text);
      if (rc) blocks.push({ kind: "roll", id: `rr-${t.turn_number}`, roll: rc });
    }

    const raw = (t.assistant_text || "").trim();
    if (!raw) continue;

    // Szybka ścieżka: brak `{` → czysta proza (odfiltruj sentinele silnika).
    if (!raw.includes("{")) {
      const p = cleanProse(raw);
      if (p) blocks.push({ kind: "gm", id: `g-${t.turn_number}`, text: p, turn: t.turn_number });
      continue;
    }

    let n = 0;
    for (const seg of extractSegments(raw)) {
      if ("text" in seg) {
        const clean = cleanProse(seg.text);
        if (clean) blocks.push({ kind: "gm", id: `g-${t.turn_number}-${n++}`, text: clean, turn: t.turn_number });
      } else {
        const o = seg.json;
        if (isRollObj(o)) {
          blocks.push({ kind: "roll", id: `r-${t.turn_number}-${n++}`, roll: rollFromObj(o) });
        } else {
          const p = objProse(o);
          if (p && !isSentinelProse(p))
            blocks.push({ kind: "gm", id: `g-${t.turn_number}-${n++}`, text: p, turn: t.turn_number });
          // obiekty cue-only (location_intent/suggested_actions) pomijamy
        }
      }
    }
  }
  return blocks;
}

// ── Odpowiedź tury → karta rzutu (F-52) ──────────────────────────────────────
// Best-effort: gdy tura zwróci `result` z polami rzutu (skill test / atak),
// budujemy kartę wg konwencji sekcji 6. Nat 20 → crit, Nat 1 → fumble.

export function rollFromResult(resp: TurnResponse | undefined): RollCardData | null {
  const r = resp?.result;
  if (!r || typeof r !== "object") return null;
  const m = r as Record<string, unknown>;
  const d20 = num(m.roll ?? m.d20, NaN);
  const total = num(m.total ?? m.sum, NaN);
  if (!Number.isFinite(d20) && !Number.isFinite(total)) return null;

  const dc = num(m.dc, NaN);
  const outcome = String(m.outcome ?? m.result ?? "").toLowerCase();
  const action = String(m.action_type ?? m.skill ?? "AKCJA").toUpperCase();
  const crit = d20 === 20 || outcome.includes("crit") || outcome.includes("kryt");
  const fumble = d20 === 1 || outcome.includes("fumble") || outcome.includes("pech");
  const success =
    outcome.includes("succ") || outcome.includes("sukces") || outcome.includes("hit");

  const cells: RollCardData["cells"] = [];
  if (Number.isFinite(d20)) cells.push({ k: "d20", v: String(d20) });
  if (Number.isFinite(total)) cells.push({ k: "Suma", v: String(total), sum: true });
  if (Number.isFinite(dc)) cells.push({ k: "DC", v: String(dc) });
  cells.push({
    k: "Wynik",
    v: crit ? "KRYTYK" : fumble ? "PECH" : success ? "SUKCES" : "PORAŻKA",
    res: true,
  });

  return {
    actor: "player",
    title: `TEST: ${action}`,
    cells,
    crit,
    fumble,
  };
}

// ── #1299 narracyjny test → karta rzutu + committed d20 (dla kości 3D) ────────
// Karta liczy sukces po stronie klienta (committed_d20 + mod ≥ DC) TYLKO do
// podglądu w overlayu. Werdykt autorytatywny (margines / opposed / omen) przychodzi
// z /skill-test/resolve i trafia do logu jako narracja GM.
export function skillTestCard(pending: SkillTestPending): {
  card: RollCardData;
  committed: number;
} {
  const raw = num(pending.committed_d20, 10);
  const committed = Math.max(1, Math.min(20, Math.round(raw)));
  const mod = num(pending.modifier_breakdown?.total, 0);
  const dc = num(pending.dc ?? pending.counter?.dc, 12);
  const total = committed + mod;
  const nat20 = committed === 20;
  const nat1 = committed === 1;
  const margin = total - dc;
  const success = nat20 || (!nat1 && total >= dc);
  // #581/#1299: margin ≥5 = „Krytyczny sukces" (mocny), ale NIE nat20 → SUKCES+ bez
  // złotej poświaty. Złoty KRYTYK / krwawy PECH tylko dla nat20/nat1.
  const marginCritSucc = !nat20 && success && margin >= 5;
  const marginCritFail = !nat1 && !success && margin <= -5;
  const name = (pending.skill_label ?? pending.skill_key ?? "Umiejętność").toUpperCase();

  const verdict = nat20
    ? "KRYTYK"
    : nat1
      ? "PECH"
      : marginCritSucc
        ? "SUKCES+"
        : marginCritFail
          ? "PORAŻKA−"
          : success
            ? "SUKCES"
            : "PORAŻKA";

  const cells: RollCardData["cells"] = [
    { k: "d20", v: String(committed) },
    { k: "Mod", v: (mod >= 0 ? "+" : "") + mod },
    { k: "Suma", v: String(total), sum: true },
    { k: "DC", v: String(dc) },
    { k: "Wynik", v: verdict, res: true, tone: success ? "ok" : "bad" },
  ];

  return {
    card: { actor: "player", title: `TEST: ${name}`, cells, crit: nat20, fumble: nat1 },
    committed,
  };
}

// ── suggested_actions → quick-action chips ───────────────────────────────────

export interface Chip {
  label: string;
  text: string;
  icon?: string;
  /** Strukturalny ciąg akcji z backendu (SEARCH / TRAVEL_RESUME / BUILD_CAMP / …). */
  action?: string;
  /** F-80: przycisk może być wyłączony (np. Kontynuuj podróż po forced_camp). */
  enabled?: boolean;
  reason?: string;
}

export function normalizeChips(actions: SuggestedAction[] | undefined): Chip[] {
  if (!actions?.length) return [];
  return actions
    .map((a): Chip | null => {
      const label = (a.label || a.text || "").trim();
      if (!label) return null;
      const action = (a.action || a.text || a.label || "").trim();
      return {
        label,
        // `text` = to, co wysyłamy jako wolny tekst (fallback); mechaniczne akcje
        // routuje Game.onChip po `action`.
        text: (a.text || a.action || a.label || "").trim(),
        action: action || undefined,
        icon: a.icon ?? undefined,
        enabled: a.enabled !== false,
        reason: a.reason ?? undefined,
      };
    })
    .filter((x): x is Chip => x !== null)
    .slice(0, 5);
}

// ── FE12 Sklep (#1261): wykrycie otwarcia sklepu z odpowiedzi tury ────────────
// Backend sygnalizuje sklep na kilka sposobów (zależnie od ścieżki): pole
// open_shop na odpowiedzi lub w result, albo sentinel [OPEN_SHOP]{json} w prozie.
export interface ShopTrigger {
  npcKey: string;
  greeting?: string | null;
}

function readNpcKey(o: unknown): ShopTrigger | null {
  if (!o || typeof o !== "object") return null;
  const r = o as Record<string, unknown>;
  const key = r.npc_key ?? r.npcKey ?? r.key;
  if (typeof key !== "string" || !key.trim()) return null;
  const greeting = r.greeting ?? r.line ?? r.hook;
  return { npcKey: key, greeting: typeof greeting === "string" ? greeting : null };
}

export function detectShop(resp: TurnResponse): ShopTrigger | null {
  const r = resp as Record<string, unknown>;
  const direct =
    readNpcKey(r.open_shop) ??
    readNpcKey((r.result as Record<string, unknown> | undefined)?.open_shop);
  if (direct) return direct;
  // Sentinel w prozie: [OPEN_SHOP]{"npc_key":"..."}
  const prose = typeof resp.prose === "string" ? resp.prose : "";
  const m = prose.match(/\[OPEN_SHOP\]\s*(\{[^\n]*\})/);
  if (m) {
    try {
      return readNpcKey(JSON.parse(m[1]));
    } catch {
      /* zignoruj zły sentinel */
    }
  }
  return null;
}
