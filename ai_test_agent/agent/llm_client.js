/**
 * Czy adres API nie wymaga typowego OPENAI_API_KEY (Ollama lokalnie/LAN/host.docker).
 * Poprzednio wymuszano klucz dla każdego URL ≠ 127.0.0.1 → decide()=null → walidator
 * daje wait_for_gm_response przy pustym chacie → timeout waitForFunction (90 s).
 */
function isApiKeyTypicallyOptional(apiUrlStr) {
  const u = String(apiUrlStr || "").toLowerCase();
  if (!u) return false;
  if (
    u.includes("127.0.0.1") ||
    u.includes("localhost") ||
    u.includes("host.docker.internal") ||
    u.includes("172.17.") ||
    u.includes("172.18.")
  ) {
    return true;
  }
  /* Ollama (OpenAI-compat i natywne API) */
  if (u.includes(":11434")) return true;
  return false;
}

const STUB_SEQUENCE = [
  {
    type: "send_chat_message",
    params: { text: "Czy możesz mi opisać otoczenie?" },
    reasoning: "stub_step_1",
    done: false,
  },
  {
    type: "wait_for_gm_response",
    params: { timeout_ms: 45_000 },
    reasoning: "stub_step_2",
    done: false,
  },
  {
    type: "send_chat_message",
    params: { text: "Jestem ranny, czy możemy przenieść się do SafeTown?" },
    reasoning: "stub_step_3",
    done: false,
  },
  {
    type: "wait_for_gm_response",
    params: { timeout_ms: 45_000 },
    reasoning: "stub_step_4",
    done: false,
  },
  {
    type: "finish",
    params: { success: false, reason: "stub_completed" },
    reasoning: "stub_end",
    done: true,
  },
];

class LLMClient {
  constructor(scenario) {
    this.stub = process.env.AI_AGENT_STUB === "1";
    this.stubIdx = 0;
    this.scenario = scenario;
    /* Domyślnie Ollama na hoście; w Dockerze nadpisz LLM_API_URL (np. host.docker.internal:11434). */
    this.apiUrl =
      process.env.LLM_API_URL || "http://127.0.0.1:11434/v1/chat/completions";
    this.apiKey = process.env.LLM_API_KEY || "";
    this.model = process.env.LLM_MODEL || "gemma4:e4b";
  }

  buildSystemPrompt() {
    const c = this.scenario.constraints || [];
    return [
      `Jesteś graczem RPG. Cel: ${this.scenario.goal}.`,
      `Persona: ${this.scenario.persona}.`,
      `Ograniczenia: ${c.join("; ")}.`,
      "Dostępne akcje: send_chat_message, wait_for_gm_response, open_screen, click, finish.",
      "Odpowiadaj WYŁĄCZNIE validnym JSON bez markdown ani komentarzy:",
      '{"type": "...", "params": {...}, "reasoning": "...", "done": false}',
      "Nie zdradzaj że jesteś AI. Nie używaj wiedzy spoza świata gry.",
    ].join("\n");
  }

  async decide(snapshot, history = []) {
    if (this.stub) {
      const i = Math.min(this.stubIdx, STUB_SEQUENCE.length - 1);
      const action = { ...STUB_SEQUENCE[i] };
      this.stubIdx += 1;
      return action;
    }
    if (!this.apiKey.trim() && !isApiKeyTypicallyOptional(this.apiUrl)) {
      console.warn(
        "[llm_client] brak LLM_API_KEY dla zewnętrznego endpointu OpenAI — zwracam null (ustaw LLM_API_KEY albo LLM_API_URL/Ollama).",
      );
      return null;
    }
    const messages = [{ role: "system", content: this.buildSystemPrompt() }];
    for (const h of history.slice(-6)) {
      messages.push({ role: "user", content: JSON.stringify(h.snapshot) });
      messages.push({ role: "assistant", content: JSON.stringify(h.action) });
    }
    messages.push({ role: "user", content: JSON.stringify(snapshot) });

    const headers = { "Content-Type": "application/json" };
    if (String(this.apiKey || "").trim()) {
      headers.Authorization = `Bearer ${this.apiKey}`;
    }
    const body = {
      model: this.model,
      messages,
      temperature: 0.7,
      max_tokens: 300,
    };
    /* Ollama: response_format bywa nieobsługiwany — zostawiamy tylko dla typowego OpenAI. */
    if (!isApiKeyTypicallyOptional(this.apiUrl) || String(this.apiUrl).includes("api.openai.com")) {
      body.response_format = { type: "json_object" };
    }

    const res = await fetch(this.apiUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      console.warn(`[llm_client] HTTP ${res.status} ${errText.slice(0, 800)}`);
      return null;
    }
    const data = await res.json();
    try {
      const text = data.choices?.[0]?.message?.content;
      if (!text) return null;
      return JSON.parse(text);
    } catch {
      console.warn("[llm_client] invalid JSON from LLM");
      return null;
    }
  }
}

module.exports = { LLMClient, STUB_SEQUENCE };
