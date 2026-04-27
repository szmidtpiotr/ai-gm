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
    this.apiUrl = process.env.LLM_API_URL || "https://api.openai.com/v1/chat/completions";
    this.apiKey = process.env.LLM_API_KEY || "";
    this.model = process.env.LLM_MODEL || "gpt-4o-mini";
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
    if (!this.apiKey.trim() && !this.apiUrl.includes("127.0.0.1")) {
      console.warn("[llm_client] brak LLM_API_KEY — zwracam null (fallback walidatora)");
      return null;
    }
    const messages = [{ role: "system", content: this.buildSystemPrompt() }];
    for (const h of history.slice(-6)) {
      messages.push({ role: "user", content: JSON.stringify(h.snapshot) });
      messages.push({ role: "assistant", content: JSON.stringify(h.action) });
    }
    messages.push({ role: "user", content: JSON.stringify(snapshot) });

    const res = await fetch(this.apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${this.apiKey}` },
      body: JSON.stringify({
        model: this.model,
        messages,
        temperature: 0.7,
        max_tokens: 300,
        response_format: { type: "json_object" },
      }),
    });
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
